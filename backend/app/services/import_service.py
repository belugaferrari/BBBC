"""Importacao de extrato: pre-visualizar, conferir, so entao gravar.

O fluxo tem dois passos de proposito. Um arquivo de banco pode vir com leiaute
inesperado, com o mesmo periodo que voce ja importou, ou com lancamentos que
voce ja digitou a mao. Gravar direto seria a maneira mais rapida de sujar a
base - e sujeira em base financeira custa horas de conferencia depois.

Passo 1 (`build_preview`): le o arquivo, marca o que ja existe e sugere
categoria. Nao grava nenhum lancamento.
Passo 2 (`confirm_import`): grava o que o usuario escolheu.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Account, Category, StatementImport, Transaction
from app.models.enums import AccountType, SocioFlow, TxDirection, TxSource, TxStatus
from app.services.caixa import caixa_da_parcela, meses_depois
from app.services.categorization import (
    Rule,
    TransactionFacts,
    categorize,
    normalize,
)
from app.services.categorization_repository import categoria_padrao, load_rules
from app.services.importers import fatura
from app.services.importers.base import ParsedTransaction, fingerprint
from app.services.importers.detect import parse_statement
from app.services.parcelas import Parcela, ler_parcela, numerar, raiz_da_descricao
from app.services.socio import (
    CONTRAPARTIDA_PADRAO,
    CONTRAPARTIDAS,
    ContrapartidaDesconhecida,
)

# Mesma janela da conciliacao do Open Finance: o banco publica alguns dias
# depois da compra, entao o lancamento manual pode estar deslocado.
MANUAL_MATCH_WINDOW_DAYS = 3

_SOURCE_BY_FORMAT = {
    "OFX": TxSource.IMPORT_OFX,
    "CSV": TxSource.IMPORT_CSV,
    "PDF": TxSource.IMPORT_PDF,
    "XLSX": TxSource.IMPORT_XLSX,
}


def _find_equivalent(db: Session, account_id: UUID, tx: ParsedTransaction) -> Transaction | None:
    """Lancamento que ja existe e corresponde a esta linha, venha de onde vier.

    Cobre os dois casos que acontecem de verdade: voce digitou a compra a mao, e
    voce ja importou o mesmo periodo em outro formato (o OFX traz FITID e o CSV
    nao, entao a impressao digital muda e so a equivalencia salva).
    """
    filtros = [
        Transaction.account_id == account_id,
        Transaction.amount == tx.amount,
        Transaction.direction == tx.direction,
        # A parcela PREVISTA nao e um lancamento repetido: ela e o lugar que
        # esta linha vem ocupar. Tratada como duplicata, a parcela de verdade
        # chegaria desmarcada na conferencia e o mes ficaria com a previsao no
        # lugar do fato - com o valor certo e o status errado, que e a forma
        # mais discreta de errar.
        Transaction.status != TxStatus.PREVISTA,
        Transaction.booked_on.between(
            tx.booked_on - timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
            tx.booked_on + timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
        ),
    ]

    # Duas parcelas da mesma compra sao gemeas em tudo o que esta olhado aqui:
    # mesma conta, mesmo valor, e a MESMA data da compra, que as faturas
    # repetem. So o numero da parcela as distingue - e sem este filtro a
    # parcela 2 chegaria marcada como "voce ja lancou este valor", desmarcada,
    # e sumiria do mes. Parcela contra lancamento sem parcela continua casando:
    # e o caso de quem digitou a compra a mao antes de a fatura chegar.
    parcela = ler_parcela(tx.description)
    if parcela:
        filtros.append(
            or_(
                Transaction.installment_no == parcela.numero,
                Transaction.installment_no.is_(None),
            )
        )

    return db.scalar(select(Transaction).where(*filtros))


def build_preview(
    db: Session,
    *,
    family_id: UUID,
    account: Account,
    member_id: UUID,
    filename: str,
    content: bytes,
) -> StatementImport:
    """Le o arquivo e monta a tela de conferencia. Nao grava lancamento algum."""
    statement = parse_statement(filename, content)
    # A fatura do cartao fala pelo lado da divida: compra positiva, pagamento
    # negativo - o contrario do extrato de conta. Precisa ser corrigida AQUI,
    # antes da impressao digital e da sugestao de categoria, porque as duas
    # dependem da direcao. Ver app/services/importers/fatura.py.
    fatura.ajustar(
        statement, e_cartao=account.type == AccountType.CARTAO_CREDITO
    )
    file_hash = hashlib.sha256(content).hexdigest()

    already = db.scalar(
        select(StatementImport).where(
            StatementImport.account_id == account.id,
            StatementImport.file_hash == file_hash,
            StatementImport.status == "CONFIRMADO",
        )
    )

    rules: list[Rule] = load_rules(db, family_id)
    category_names = {
        row.id: row.name
        for row in db.scalars(
            select(Category).where(Category.family_id.in_([family_id, None]))
        ).all()
    }
    # Para onde vai o que nenhuma regra reconheceu - depende da direcao e do TIPO
    # da conta (ver `categoria_padrao`). Fica fora do laco de proposito: duas
    # consultas uma vez, e nao duas por linha do extrato.
    tipo_da_conta = account.type.value if account.type else None
    a_definir = {
        direcao: categoria_padrao(db, family_id, direcao, tipo_da_conta)
        for direcao in (TxDirection.SAIDA, TxDirection.ENTRADA)
    }

    # O VENCIMENTO DA FATURA, quando o arquivo diz qual e.
    #
    # Toda compra de uma fatura sai da conta no mesmo dia: o dia em que a fatura
    # e paga. Sabendo esse dia, nao ha o que calcular - e some de uma vez a
    # classe inteira de erro de "em que mes isto cai", inclusive a parcela
    # antiga, cuja data de compra e de meses atras e nao diz nada sobre quando
    # ela e cobrada.
    vencimento_da_fatura = (
        statement.vencimento
        if statement.vencimento and account.type == AccountType.CARTAO_CREDITO
        else None
    )
    if vencimento_da_fatura:
        statement.warnings.append(
            f"A fatura diz que vence em {vencimento_da_fatura:%d/%m/%Y}: todas as "
            "compras deste arquivo contam nesse mes, que e quando o dinheiro sai "
            "da conta."
        )

    preview: list[dict] = []
    duplicates = 0

    for index, tx in enumerate(statement.transactions):
        digital = fingerprint(account.id, tx)

        existing = db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.import_fingerprint == digital,
            )
        )
        equivalent = None if existing else _find_equivalent(db, account.id, tx)
        duplicate_reason = None
        if existing:
            duplicate_reason = "ja importado antes"
        elif equivalent is not None:
            duplicate_reason = (
                "ja importado em outro formato"
                if equivalent.import_id is not None
                else "voce ja lancou este valor a mao"
            )
        if duplicate_reason:
            duplicates += 1

        match = categorize(
            TransactionFacts(
                description=tx.description,
                amount=tx.amount,
                direction=tx.direction,
                account_id=account.id,
            ),
            rules,
        )
        # Sem regra que reconheca, a categoria sugerida e "A definir": melhor um
        # lugar visivel para o pendente que categoria nenhuma.
        sugerida = match.category_id if match else a_definir.get(tx.direction)

        # A parcela, venha ela de onde vier: de uma coluna propria do extrato
        # (a fatura do Itau traz "Parcela 2 de 10" assim) ou escrita dentro da
        # descricao. A linha vale R$ 300, mas a COMPRA foi de R$ 3.000 - e ainda
        # faltam oito meses dela.
        parcela = parcela_da_linha(tx)

        preview.append(
            {
                "index": index,
                "booked_on": tx.booked_on.isoformat(),
                # Quando este valor sai da conta. No cartao e o vencimento da
                # fatura, e e o mes em que o Resumo vai contar - entao tem de
                # estar na tela ANTES de confirmar.
                "paid_on": _quando_sai_da_conta(
                    account, tx, parcela, vencimento_da_fatura
                ).isoformat(),
                "amount": str(tx.amount),
                "direction": tx.direction.value,
                "description": tx.description,
                "document": tx.document,
                "installment_no": parcela.numero if parcela else None,
                "installment_total": parcela.total if parcela else None,
                "valor_da_compra": (
                    str(parcela.valor_da_compra(tx.amount)) if parcela else None
                ),
                "parcelas_faltando": parcela.quantas_faltam if parcela else 0,
                "fingerprint": digital,
                "duplicate": duplicate_reason is not None,
                "duplicate_reason": duplicate_reason,
                "matched_transaction_id": str(equivalent.id) if equivalent else None,
                "suggested_category_id": str(sugerida) if sugerida else None,
                "suggested_category_name": category_names.get(sugerida),
                # A tela precisa distinguir as duas coisas: sugestao e um palpite
                # com base em algo ("MERCADO X" -> Mercado), e "A definir" e a
                # ausencia de palpite. Mostradas iguais, a segunda passaria por
                # sugestao e seria confirmada sem ninguem olhar.
                "suggested_is_pending": match is None,
                "confidence": str(match.confidence) if match else None,
                # marcado por padrao: o que nao e duplicado entra
                "selected": duplicate_reason is None,
            }
        )

    warnings = list(statement.warnings)
    if already:
        warnings.insert(
            0,
            f"Este mesmo arquivo ja foi importado em "
            f"{already.confirmed_at:%d/%m/%Y}. Os lancamentos repetidos estao desmarcados.",
        )

    row = StatementImport(
        family_id=family_id,
        account_id=account.id,
        uploaded_by=member_id,
        filename=filename or "extrato",
        file_format=statement.file_format,
        file_hash=file_hash,
        file_size=len(content),
        status="CRIADO",
        period_start=statement.period_start,
        period_end=statement.period_end,
        rows_detected=len(statement.transactions),
        rows_duplicated=duplicates,
        preview=preview,
        warnings=warnings,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def parcela_da_linha(tx: ParsedTransaction) -> Parcela | None:
    """A parcela desta linha, da coluna propria ou da descricao.

    A coluna vem primeiro porque e o banco afirmando, e nao o leitor deduzindo
    de um texto que tambem pode ser uma data.
    """
    if tx.installment_no and tx.installment_total:
        return Parcela(numero=tx.installment_no, total=tx.installment_total)
    return ler_parcela(tx.description)


def _quando_sai_da_conta(
    account: Account,
    tx: ParsedTransaction,
    parcela: Parcela | None,
    vencimento_da_fatura: date | None,
) -> date:
    """O dia em que o dinheiro desta linha sai da conta.

    Com o vencimento escrito no arquivo, nao ha conta a fazer: toda COMPRA de
    uma fatura e cobrada no dia em que a fatura e paga, seja ela de ontem ou a
    sexta parcela de algo comprado ano passado. E o que conserta, de uma vez, a
    parcela antiga que caia num mes em que nada saiu da conta.

    O credito dentro da fatura e a excecao: a linha "Pagamento Efetuado" e o
    pagamento da fatura ANTERIOR, e aconteceu no dia dela. Carimba-la com este
    vencimento seria mover para ca um dinheiro que saiu no mes passado.
    """
    if vencimento_da_fatura and tx.direction == TxDirection.SAIDA:
        return vencimento_da_fatura
    return caixa_da_parcela(
        account, tx.booked_on, tx.direction, parcela.numero if parcela else None
    )


def _previsao_que_esta_parcela_vem_ocupar(
    db: Session, account_id: UUID, descricao: str, parcela: Parcela
) -> Transaction | None:
    """A parcela prevista que esta linha de fatura vem substituir.

    Quando a fatura de outubro trouxe "PARCELA 02/10", o sistema criou as oito
    seguintes como PREVISTA, cada uma no mes em que vai cair. Agora chegou a
    fatura de novembro com a "03/10": ela e a mesma parcela, de verdade. Sem
    reconhecer isso, o mes de novembro teria as duas - a prevista e a real - e
    contaria a parcela duas vezes.

    O casamento e por conta, numero da parcela, total e RAIZ da descricao: as
    duas linhas falam da mesma compra, mas escrevem a parcela de jeitos
    diferentes ("PARCELA 03/10" contra "(3/10)").
    """
    candidatas = db.scalars(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.status == TxStatus.PREVISTA,
            Transaction.installment_no == parcela.numero,
            Transaction.installment_total == parcela.total,
        )
    ).all()
    raiz = raiz_da_descricao(descricao)
    for candidata in candidatas:
        if raiz_da_descricao(candidata.description) == raiz:
            return candidata
    return None


def _prever_as_parcelas_que_faltam(
    db: Session, base: Transaction, parcela: Parcela
) -> int:
    """Cria as proximas parcelas como PREVISTA, cada uma no mes em que vai cair.

    "Contas parceladas devem aparecer em todos os meses em que ainda estao
    vigentes as parcelas." Cada fatura futura vai trazer a parcela dela, mas ate
    la essas faturas nao existem - e o compromisso ja existe. Elas nascem
    PREVISTA porque e o que sao: dinheiro que vai sair, e que ainda nao saiu.

    Toda consulta de dinheiro do sistema filtra por EFETIVADA/CONCILIADA, entao
    nenhuma delas entra no gasto de mes nenhum por engano - elas aparecem onde
    compromisso aparece, que e a Previsao.
    """
    criadas = 0
    for numero in range(parcela.numero + 1, parcela.total + 1):
        seguinte = Parcela(numero=numero, total=parcela.total)
        db.add(
            Transaction(
                family_id=base.family_id,
                account_id=base.account_id,
                owner_member_id=base.owner_member_id,
                category_id=base.category_id,
                # a compra continua sendo a mesma, no dia em que foi feita
                booked_on=base.booked_on,
                paid_on=meses_depois(base.paid_on, numero - parcela.numero),
                amount=base.amount,
                direction=base.direction,
                description=numerar(base.description, seguinte),
                description_norm=normalize(numerar(base.description, seguinte)),
                status=TxStatus.PREVISTA,
                source=base.source,
                import_id=base.import_id,
                # Sem impressao digital: ela identifica uma linha de extrato, e
                # esta nao veio de nenhuma. Repeti-la bateria no indice unico.
                import_fingerprint=None,
                installment_no=numero,
                installment_total=parcela.total,
                installment_group=base.installment_group,
                ir_year=base.booked_on.year,
                socio_flow=base.socio_flow,
            )
        )
        criadas += 1
    return criadas


def _direcao_conferida(
    account_id: UUID, item: dict, escolhida: str | None
) -> tuple[TxDirection, str]:
    """A direcao da linha e a impressao digital que corresponde a ela.

    Virar a direcao muda a impressao digital, porque ela e calculada com a
    direcao dentro (ver `fingerprint`). Guardar a antiga faria a mesma linha,
    reimportada no mes seguinte, parecer uma linha nova - e o gasto entraria
    duas vezes.
    """
    direcao = TxDirection(escolhida) if escolhida else TxDirection(item["direction"])
    if escolhida is None or direcao == TxDirection(item["direction"]):
        return direcao, item["fingerprint"]

    digital = fingerprint(
        account_id,
        ParsedTransaction(
            booked_on=datetime.fromisoformat(item["booked_on"]).date(),
            amount=Decimal(item["amount"]),
            direction=direcao,
            description=item["description"],
            document=item.get("document"),
        ),
    )
    return direcao, digital


def _categoria_por_path(db: Session, family_id: UUID, path: str) -> Category | None:
    """A copia da familia primeiro; o catalogo global so como reserva."""
    return db.scalar(
        select(Category)
        .where(Category.path == path, Category.family_id.in_((family_id, None)))
        # family_id NULL por ultimo: a copia da familia manda
        .order_by(Category.family_id.is_(None))
    )


def confirm_import(
    db: Session,
    row: StatementImport,
    *,
    selected_indexes: list[int] | None = None,
    category_overrides: dict[int, UUID] | None = None,
    direction_overrides: dict[int, str] | None = None,
    vencimento_da_fatura: date | None = None,
    contrapartidas: dict[int, str] | None = None,
) -> StatementImport:
    """Grava os lancamentos escolhidos na tela de conferencia.

    Numa conta da empresa, confirmar uma linha quer dizer "isto e meu": o que
    fica de fora e o que pertence a empresa. Cada linha confirmada ali vira um
    PAR - a despesa na categoria escolhida e a entrada que a cobre - para o
    caixa da familia nao cair por um gasto que nao saiu do bolso dela. Ver
    app/services/socio.py.
    """
    if row.status == "CONFIRMADO":
        raise ValueError("esta importacao ja foi confirmada")

    account = db.get(Account, row.account_id)
    overrides = category_overrides or {}
    chosen = (
        set(selected_indexes)
        if selected_indexes is not None
        else {item["index"] for item in row.preview if item["selected"]}
    )

    created = 0
    for item in row.preview:
        index = item["index"]
        if index not in chosen:
            continue

        booked_on = datetime.fromisoformat(item["booked_on"]).date()
        amount = Decimal(item["amount"])
        # A direcao pode ter sido virada na conferencia. A impressao digital vai
        # junto, porque a direcao faz parte dela: mantida a antiga, a mesma linha
        # reimportada no mes seguinte pareceria linha nova.
        direction, digital = _direcao_conferida(
            account.id, item, (direction_overrides or {}).get(index)
        )

        # A guarda final e o indice unico em (account_id, import_fingerprint):
        # mesmo com duas confirmacoes simultaneas, a linha nao duplica.
        if db.scalar(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.import_fingerprint == digital,
            )
        ):
            continue

        confianca = item["confidence"]
        if index in overrides:
            category_id = overrides[index]
        elif direction != TxDirection(item["direction"]):
            # Virou de lado e ninguem escolheu categoria: a sugestao da
            # pre-visualizacao era do OUTRO lado, e gravar "Salario" numa saida
            # seria trocar um erro por um pior - o que erra do lado da receita
            # ainda estraga a renda do mes e o IR. Vai para "A definir", que
            # aparece no Resumo cobrando.
            category_id = categoria_padrao(
                db,
                row.family_id,
                direction,
                account.type.value if account.type else None,
            )
            # a confianca era da sugestao que acabou de ser descartada
            confianca = None
        else:
            category_id = (
                UUID(item["suggested_category_id"]) if item["suggested_category_id"] else None
            )
        description = item["description"]
        da_empresa = bool(getattr(account, "is_business", False))
        # A parcela que a conferencia ja tinha lido - da coluna propria do
        # extrato ou da descricao. Ver app/services/parcelas.py.
        #
        # So no CARTAO as parcelas que faltam viram compromisso gravado. Num
        # extrato de conta corrente, "1/3" tanto pode ser um carne quanto um
        # numero que o banco escreveu por outro motivo - e inventar dois gastos
        # futuros a partir de um palpite e pior do que nao inventar nenhum. A
        # leitura da parcela continua valendo para a tela, em qualquer conta.
        parcela = (
            Parcela(numero=item["installment_no"], total=item["installment_total"])
            if item.get("installment_no") and item.get("installment_total")
            else None
        )
        e_cartao = account.type == AccountType.CARTAO_CREDITO
        parcela_a_prever = parcela if (parcela and e_cartao) else None

        # A data de caixa e a que ELE VIU na conferencia - nao uma conta refeita
        # agora. O que foi conferido e o que e gravado; recalcular aqui abriria
        # a porta para o mes mudar entre a tela e o banco, que e a surpresa mais
        # cara que este sistema pode dar.
        #
        # Duas excecoes: ele trocou o vencimento da fatura na tela, ou virou o
        # lado da linha (e ai a data de caixa de antes era a da outra direcao).
        if vencimento_da_fatura and direction == TxDirection.SAIDA and e_cartao:
            paid_on = vencimento_da_fatura
        elif item.get("paid_on") and direction == TxDirection(item["direction"]):
            paid_on = datetime.fromisoformat(item["paid_on"]).date()
        else:
            paid_on = caixa_da_parcela(
                account, booked_on, direction, parcela.numero if parcela else None
            )
        prevista = (
            _previsao_que_esta_parcela_vem_ocupar(db, account.id, description, parcela)
            if parcela_a_prever
            else None
        )

        lancamento = Transaction(
            family_id=row.family_id,
            account_id=account.id,
            owner_member_id=account.owner_member_id,
            category_id=category_id,
            booked_on=booked_on,
            paid_on=paid_on,
            amount=amount,
            direction=direction,
            description=description,
            description_norm=normalize(description),
            status=TxStatus.EFETIVADA,
            source=_SOURCE_BY_FORMAT[row.file_format],
            import_id=row.id,
            import_fingerprint=digital,
            ir_year=booked_on.year,
            auto_confidence=Decimal(confianca) if confianca else None,
            socio_flow=SocioFlow.PESSOAL_VIA_EMPRESA if da_empresa else None,
            installment_no=parcela.numero if parcela else None,
            installment_total=parcela.total if parcela else None,
            # as parcelas de uma compra andam juntas por este identificador
            installment_group=(
                prevista.installment_group
                if prevista
                else (uuid4() if parcela_a_prever else None)
            ),
        )
        db.add(lancamento)
        created += 1

        if parcela_a_prever:
            if prevista is not None:
                # A parcela de verdade chegou: a previsao sai de cena, com as
                # irmas dela intactas. Apagar e melhor que marcar como
                # cumprida - uma previsao cumprida nao e dado nenhum, e duas
                # linhas para a mesma parcela e exatamente o que se quer evitar.
                db.delete(prevista)
            else:
                # primeira vez que esta compra aparece: as parcelas que faltam
                # viram compromisso, cada uma no mes em que vai sair
                db.flush()
                _prever_as_parcelas_que_faltam(db, lancamento, parcela_a_prever)

        # So despesa gera par. Uma ENTRADA na conta da empresa confirmada como
        # minha ja e o dinheiro chegando (pro-labore, lucro): criar contrapartida
        # ali dobraria a receita.
        if da_empresa and direction == TxDirection.SAIDA:
            escolha = (contrapartidas or {}).get(index, CONTRAPARTIDA_PADRAO)
            if escolha not in CONTRAPARTIDAS:
                raise ContrapartidaDesconhecida(
                    f"contrapartida '{escolha}' desconhecida na linha {index}"
                )
            contra_cat = _categoria_por_path(db, row.family_id, CONTRAPARTIDAS[escolha])
            db.flush()  # precisa do id da despesa para ligar o par
            db.add(
                Transaction(
                    family_id=row.family_id,
                    account_id=account.id,
                    owner_member_id=account.owner_member_id,
                    category_id=contra_cat.id if contra_cat else None,
                    booked_on=booked_on,
                    # a contrapartida acompanha a despesa que ela cobre: as duas
                    # tem de cair no mesmo mes, ou o caixa da familia balanca
                    paid_on=lancamento.paid_on,
                    amount=amount,
                    direction=TxDirection.ENTRADA,
                    description=f"Pago pela empresa: {description}",
                    description_norm=normalize(f"Pago pela empresa: {description}"),
                    status=TxStatus.EFETIVADA,
                    source=_SOURCE_BY_FORMAT[row.file_format],
                    import_id=row.id,
                    # Sem impressao digital: ela identifica a linha do extrato, e
                    # esta nao veio de linha nenhuma. Repeti-la bateria no indice
                    # unico e impediria a propria despesa de ser gravada.
                    import_fingerprint=None,
                    ir_year=booked_on.year,
                    socio_flow=SocioFlow.PESSOAL_VIA_EMPRESA,
                    transfer_pair_id=lancamento.id,
                )
            )

    row.rows_imported = created
    row.status = "CONFIRMADO"
    row.confirmed_at = datetime.now(UTC)
    db.flush()

    recompute_account_balance(db, account)
    return row


def recompute_account_balance(db: Session, account: Account) -> Decimal:
    """Recalcula o saldo materializado a partir do razao da conta."""
    rows = db.scalars(
        select(Transaction).where(
            Transaction.account_id == account.id,
            Transaction.status.in_([TxStatus.EFETIVADA, TxStatus.CONCILIADA]),
        )
    ).all()
    balance = sum((tx.signed_amount for tx in rows), Decimal("0"))
    account.current_balance = balance
    db.flush()
    return balance
