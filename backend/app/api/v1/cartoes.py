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

    # A vigilancia: linha que PARECE pagamento de fatura e que, do jeito que
    # esta classificada, esta sendo contada como gasto. Cada uma dessas e uma
    # fatura inteira somada em cima das compras que ela paga.
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

    return {
        "month": mes,
        "total_spent": brl(total),
        "cards": cartoes,
        "bill_paid": brl(fatura_paga),
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
