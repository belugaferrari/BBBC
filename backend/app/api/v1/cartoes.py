"""Cartao de credito: quanto foi gasto, e a vigilancia contra contar duas vezes.

O cartao e o unico lugar do sistema onde o MESMO dinheiro aparece em dois
extratos. A compra entra no extrato do cartao no dia em que acontece; semanas
depois, o pagamento da fatura entra no extrato da conta corrente. Importar os
dois e o caminho normal - e, sem cuidado, cada compra seria contada duas vezes e
o mes dobraria de tamanho.

A regra que resolve isso e simples de dizer e facil de violar sem perceber:

    a DESPESA e a compra, no dia dela.
    o pagamento da fatura e TRANSFERENCIA de bolso, e nao gasto.

O que a categoria 'Pagamento de fatura' faz, com `counts_as_expense = false`. As
contas fecham sozinhas quando a linha da fatura esta classificada ali. Quando
nao esta - porque o banco escreveu a descricao de um jeito que nenhuma regra
reconheceu - ninguem avisa, e e justamente esse silencio que este modulo quebra:
o `/cards/summary` devolve as linhas suspeitas junto com os numeros.

E TEM O SILENCIO CONTRARIO, que e pior porque parece bom: quando a fatura e paga
e as compras NAO foram importadas, aquela regra faz o gasto do cartao
desaparecer. O extrato de conta corrente dele traz o cartao como uma linha so, o
total pago, sem detalhe - entao, sem a fatura importada, saem milhares de reais
da conta e o mes nao registra gasto nenhum. O mes fica barato no papel.

Por isso o resumo compara as duas coisas: quanto de fatura foi PAGA no mes e
quanto de compra de cartao o sistema CONHECE na janela que essa fatura cobre.
Compra conhecida zero com fatura paga e um buraco do tamanho da fatura, e vem
escrito. A saida oferecida e classificar o pagamento como "Cartao (sem
detalhe)", que conta como gasto num valor so - e, se um dia a fatura for
importada, a vigilancia passa a apontar aquela linha como duplicata.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import CurrentMember, DbSession
from app.services.analise_categoria import brl, primeiro_do_mes

router = APIRouter(prefix="/cards", tags=["cartoes"])

# Como o banco costuma escrever a linha do pagamento da fatura. Serve para
# procurar a linha que o motor de categorizacao deixou passar - nao para
# classificar nada, que e trabalho das regras de fornecedor.
_JEITOS_DE_ESCREVER_FATURA = (
    "%fatura%",
    "%pagamento%cartao%",
    "%pag%cartao%",
)


@router.get("/summary")
def card_summary(
    current: CurrentMember, db: DbSession, month: date | None = None
) -> dict:
    """Gasto no cartao no mes, por cartao, e o que pode estar contado em dobro.

    O gasto e a soma das COMPRAS lancadas nas contas do tipo cartao de credito -
    e nao o valor da fatura. Os dois quase nunca sao iguais: a fatura que chega
    em novembro cobra compras de outubro, e e o mes da compra que importa para
    saber onde o dinheiro foi.
    """
    mes = primeiro_do_mes(month or date.today())

    por_cartao = db.execute(
        text(
            """
            SELECT a.id, a.name, a.credit_limit, a.statement_close_day,
                   a.statement_due_day,
                   COALESCE(SUM(t.amount), 0) AS gasto,
                   COUNT(t.id)                AS lancamentos
              FROM accounts a
              LEFT JOIN transactions t
                     ON t.account_id = a.id
                    AND t.direction = 'SAIDA'
                    AND t.status IN ('EFETIVADA', 'CONCILIADA')
                    AND date_trunc('month', t.booked_on)
                        = date_trunc('month', CAST(:mes AS date))
                    AND t.id NOT IN (
                        SELECT t2.id FROM transactions t2
                          JOIN categories c2 ON c2.id = t2.category_id
                         WHERE c2.counts_as_expense = false
                    )
             WHERE a.family_id = :familia
               AND a.type = 'CARTAO_CREDITO'
               AND a.is_archived = false
             GROUP BY a.id, a.name, a.credit_limit, a.statement_close_day,
                      a.statement_due_day
             ORDER BY 6 DESC, a.name
            """
        ),
        {"familia": current.family_id, "mes": mes},
    ).mappings().all()

    # O que foi pago de fatura no mes: sai da conta corrente, e NAO e gasto.
    # Aparece aqui so para o numero poder ser conferido contra o extrato.
    fatura_paga = db.execute(
        text(
            """
            SELECT COALESCE(SUM(t.amount), 0)
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND c.path <@ 'transferencias.pagamento_cartao'::ltree
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND date_trunc('month', t.booked_on)
                   = date_trunc('month', CAST(:mes AS date))
            """
        ),
        {"familia": current.family_id, "mes": mes},
    ).scalar_one()

    # Quanto de compra de cartao o sistema conhece na janela que a fatura paga
    # neste mes cobre: o mes anterior e este. A fatura que vence em outubro cobra
    # compras de setembro (e o comeco de outubro, se o fechamento for no meio do
    # mes), entao comparar so dentro do mes do pagamento acusaria buraco todo
    # mes, inclusive quando nao ha nenhum.
    compras_na_janela = db.execute(
        text(
            """
            SELECT COALESCE(SUM(t.amount), 0)
              FROM transactions t
              JOIN accounts a ON a.id = t.account_id
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND a.type = 'CARTAO_CREDITO'
               AND t.direction = 'SAIDA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND COALESCE(c.counts_as_expense, true)
               AND t.booked_on >= (CAST(:mes AS date) - INTERVAL '1 month')
               AND t.booked_on < (CAST(:mes AS date) + INTERVAL '1 month')
            """
        ),
        {"familia": current.family_id, "mes": mes},
    ).scalar_one()

    # O que ele decidiu contar como gasto sem detalhar. Fica visivel para a
    # conta poder ser desfeita no dia em que a fatura for importada.
    sem_detalhe = db.execute(
        text(
            """
            SELECT COALESCE(SUM(t.amount), 0)
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND c.path = 'despesas.cartao_sem_detalhe'::ltree
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND date_trunc('month', t.booked_on)
                   = date_trunc('month', CAST(:mes AS date))
            """
        ),
        {"familia": current.family_id, "mes": mes},
    ).scalar_one()

    # As linhas de pagamento de fatura do mes, para a tela poder oferecer "contar
    # como gasto" quando o detalhe nao vai vir.
    pagamentos = db.execute(
        text(
            """
            SELECT t.id, t.booked_on, t.amount, t.description,
                   c.path::text AS category_path
              FROM transactions t
              JOIN categories c ON c.id = t.category_id
              JOIN accounts a ON a.id = t.account_id
             WHERE t.family_id = :familia
               AND t.direction = 'SAIDA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND a.type <> 'CARTAO_CREDITO'
               AND (c.path <@ 'transferencias.pagamento_cartao'::ltree
                    OR c.path = 'despesas.cartao_sem_detalhe'::ltree)
               AND date_trunc('month', t.booked_on)
                   = date_trunc('month', CAST(:mes AS date))
             ORDER BY t.amount DESC
            """
        ),
        {"familia": current.family_id, "mes": mes},
    ).mappings().all()

    # A vigilancia: linha que PARECE pagamento de fatura e que, do jeito que
    # esta classificada, esta sendo contada como gasto. Cada uma dessas e uma
    # fatura inteira somada em cima das compras que ela paga.
    #
    # "Cartao (sem detalhe)" fica de fora enquanto nao houver compra conhecida na
    # janela: ali contar como gasto e a decisao certa, e acusar duplicata seria
    # reclamar do que o sistema mesmo sugeriu. Com compra conhecida, volta a ser
    # duplicata de verdade - e a tela diz isso.
    suspeitas = db.execute(
        text(
            """
            SELECT t.id, t.booked_on, t.amount, t.description,
                   a.name AS account_name, a.type::text AS account_type,
                   c.name AS category_name
              FROM transactions t
              JOIN accounts a ON a.id = t.account_id
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :familia
               AND t.direction = 'SAIDA'
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND COALESCE(c.counts_as_expense, true)
               AND a.type <> 'CARTAO_CREDITO'
               AND NOT (c.path = 'despesas.cartao_sem_detalhe'::ltree
                        AND :compras_conhecidas = 0)
               AND date_trunc('month', t.booked_on)
                   = date_trunc('month', CAST(:mes AS date))
               AND (
                   lower(t.description) LIKE :jeito1
                OR lower(t.description) LIKE :jeito2
                OR lower(t.description) LIKE :jeito3
               )
             ORDER BY t.amount DESC
            """
        ),
        {
            "familia": current.family_id,
            "mes": mes,
            "compras_conhecidas": compras_na_janela,
            "jeito1": _JEITOS_DE_ESCREVER_FATURA[0],
            "jeito2": _JEITOS_DE_ESCREVER_FATURA[1],
            "jeito3": _JEITOS_DE_ESCREVER_FATURA[2],
        },
    ).mappings().all()

    cartoes = [
        {
            "id": linha["id"],
            "name": linha["name"],
            "credit_limit": linha["credit_limit"],
            "statement_close_day": linha["statement_close_day"],
            "statement_due_day": linha["statement_due_day"],
            "spent": brl(linha["gasto"]),
            "transactions": int(linha["lancamentos"]),
            # Pontos costumam ser por real gasto; o fator exato esta em
            # /card-programs, e aqui fica a base sobre a qual ele incide.
            "points_base": brl(linha["gasto"]),
        }
        for linha in por_cartao
    ]
    total = sum((Decimal(c["spent"]) for c in cartoes), Decimal("0.00"))

    # O buraco: fatura paga sem compra conhecida na janela. Dinheiro que saiu da
    # conta e nao esta em gasto nenhum.
    buraco = brl(fatura_paga) if brl(compras_na_janela) == Decimal("0.00") else Decimal("0.00")

    return {
        "month": mes,
        "total_spent": brl(total),
        "cards": cartoes,
        "bill_paid": brl(fatura_paga),
        # Quanto de compra de cartao o sistema conhece na janela que a fatura
        # cobre (mes anterior e este).
        "purchases_known": brl(compras_na_janela),
        "sem_detalhe": brl(sem_detalhe),
        "gap": buraco,
        "bill_payments": [
            {
                "id": linha["id"],
                "booked_on": linha["booked_on"],
                "amount": brl(linha["amount"]),
                "description": linha["description"],
                # true quando ele ja escolheu contar esta linha como gasto
                "counted_as_expense": linha["category_path"]
                == "despesas.cartao_sem_detalhe",
            }
            for linha in pagamentos
        ],
        "aviso_sem_detalhe": (
            f"Foram pagos {brl(fatura_paga)} de fatura neste mês e o sistema não "
            "conhece nenhuma compra de cartão no período que ela cobre. Esse "
            "dinheiro saiu da conta e não está em gasto nenhum: ou você importa "
            "a fatura do cartão (o detalhe, compra por compra), ou marca o "
            "pagamento como “Cartão (sem detalhe)” para ele contar como um gasto "
            "só. Do jeito que está, o mês parece mais barato do que foi."
            if buraco > 0
            else None
        ),
        "possible_duplicates": [
            {
                "id": linha["id"],
                "booked_on": linha["booked_on"],
                "amount": brl(linha["amount"]),
                "description": linha["description"],
                "account_name": linha["account_name"],
                "category_name": linha["category_name"],
            }
            for linha in suspeitas
        ],
        "aviso": (
            "Estas linhas parecem pagamento de fatura e estão contando como "
            "gasto. Cada uma soma a fatura inteira em cima das compras que ela "
            "paga — mude a categoria para 'Pagamento de fatura'."
            if suspeitas
            else None
        ),
    }
