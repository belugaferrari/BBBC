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
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, StatementImport, Transaction
from app.models.enums import AccountType, SocioFlow, TxDirection, TxSource, TxStatus
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
    return db.scalar(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.amount == tx.amount,
            Transaction.direction == tx.direction,
            Transaction.booked_on.between(
                tx.booked_on - timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
                tx.booked_on + timedelta(days=MANUAL_MATCH_WINDOW_DAYS),
            ),
        )
    )


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

        preview.append(
            {
                "index": index,
                "booked_on": tx.booked_on.isoformat(),
                "amount": str(tx.amount),
                "direction": tx.direction.value,
                "description": tx.description,
                "document": tx.document,
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

        lancamento = Transaction(
            family_id=row.family_id,
            account_id=account.id,
            owner_member_id=account.owner_member_id,
            category_id=category_id,
            booked_on=booked_on,
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
        )
        db.add(lancamento)
        created += 1

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
