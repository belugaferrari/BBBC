"""Consultas agregadas. SQL explicito onde o ORM atrapalharia a leitura.

O MES, aqui, e sempre o do `paid_on` - o dia em que o dinheiro SAI DA CONTA -, e
nunca o do `booked_on`, que e o dia em que a compra aconteceu. Em conta corrente
os dois sao iguais; no cartao, a compra de 25 de setembro sai da conta no
vencimento da fatura de outubro, e e em outubro que ela pesa.

E a regra que ele pediu, e a razao e que o Resumo precisa fechar com o extrato
bancario - o documento contra o qual ele confere. Uma compra parcelada cai
sozinha nesse desenho: cada fatura cobra uma parcela, e cada parcela sai da conta
no vencimento da sua fatura, entao as parcelas se distribuem pelos meses sem
ninguem espalhar nada. Ver app/services/caixa.py.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.caixa import meses_depois
from app.services.mascara import nome_curto
from app.services.money import ZERO, brl
from app.services.sankey import FlowRow

_SCOPE_FILTER = (
    "AND (CAST(:member_id AS uuid) IS NULL "
    "OR t.owner_member_id = CAST(:member_id AS uuid))"
)


def consolidated_balances(db: Session, family_id: UUID, member_id: UUID | None) -> dict:
    rows = db.execute(
        text(
            """
            SELECT a.type::text AS type,
                   a.is_business,
                   SUM(a.current_balance) AS total,
                   COUNT(*)               AS accounts
              FROM accounts a
             WHERE a.family_id = :family_id
               AND a.is_archived = false
               AND (CAST(:member_id AS uuid) IS NULL
                    OR a.owner_member_id = CAST(:member_id AS uuid) OR a.is_shared)
             GROUP BY a.type, a.is_business
            """
        ),
        {"family_id": family_id, "member_id": member_id},
    ).mappings().all()

    # A CONTA DA EMPRESA fica de fora, e isso estava prometido desde a migration
    # 0007 ("o saldo nao entra no patrimonio da familia") sem nunca ter sido
    # feito. O dinheiro da empresa nao e da familia: ele tem socio, tem imposto
    # para sair de la, e some no dia em que a empresa gastar. Somado ao
    # patrimonio, inflava justamente o numero que serve para decidir se da para
    # comprar alguma coisa.
    #
    # Enquanto a conta fosse do tipo "PJ" o erro nao aparecia - PJ nao cai em
    # nenhum dos baldes somados abaixo. Bastava cadastrar a conta da empresa
    # como conta corrente, que e o que ela e, para o saldo inteiro entrar.
    na_empresa = sum((brl(r["total"] or 0) for r in rows if r["is_business"]), ZERO)
    by_type: dict[str, Decimal] = {}
    for r in rows:
        if r["is_business"]:
            continue
        by_type[r["type"]] = by_type.get(r["type"], ZERO) + brl(r["total"] or 0)

    liquid = sum(
        (v for k, v in by_type.items() if k in {"CONTA_CORRENTE", "POUPANCA", "DINHEIRO"}),
        ZERO,
    )
    card_debt = -by_type.get("CARTAO_CREDITO", ZERO)
    invested = by_type.get("INVESTIMENTO", ZERO)
    return {
        "by_type": by_type,
        "liquid": brl(liquid),
        "credit_card_debt": brl(card_debt),
        "invested": brl(invested),
        "net_worth": brl(liquid + invested - card_debt),
        # O dinheiro que esta na empresa. Nao entra em nada acima, e esta aqui
        # para a tela poder dizer onde ele esta - em vez de ele sumir, que e o
        # jeito mais rapido de alguem achar que o sistema perdeu um saldo.
        "na_empresa": brl(na_empresa),
    }


# Quanto das doacoes com destino foi de fato coberto pelo gasto daquele destino.
#
# Sem o limite, uma doacao de 3.000 "para a escola" num mes em que a escola
# custou 1.000 abateria 3.000 do consumo da familia - e o mes apareceria melhor
# do que foi. O `LEAST` corta no que realmente se gastou: a doacao cobre ate onde
# houve o que cobrir.
_DOACOES_APLICADAS = f"""
    WITH recebidas AS (
        SELECT t.donation_for_category_id AS categoria,
               SUM(t.amount)              AS valor
          FROM transactions t
         WHERE t.family_id = :family_id
           AND t.direction = 'ENTRADA'
           AND t.status IN ('EFETIVADA', 'CONCILIADA')
           AND t.donation_for_category_id IS NOT NULL
           AND date_trunc('month', t.paid_on)
               = date_trunc('month', CAST(:month AS date))
           {_SCOPE_FILTER}
         GROUP BY 1
    ),
    gasto_no_destino AS (
        SELECT r.categoria,
               COALESCE(SUM(g.amount), 0) AS gasto
          FROM recebidas r
          JOIN categories alvo ON alvo.id = r.categoria
          LEFT JOIN categories filha
                 ON filha.family_id = alvo.family_id
                AND filha.path <@ alvo.path
          LEFT JOIN transactions g
                 ON g.category_id = filha.id
                AND g.direction = 'SAIDA'
                AND g.status IN ('EFETIVADA', 'CONCILIADA')
                AND COALESCE(filha.counts_as_expense, true)
                AND date_trunc('month', g.paid_on)
                    = date_trunc('month', CAST(:month AS date))
         GROUP BY r.categoria
    )
    SELECT COALESCE(SUM(LEAST(r.valor, d.gasto)), 0)
      FROM recebidas r
      JOIN gasto_no_destino d ON d.categoria = r.categoria
"""


# Quanto dos gastos DO MES ja voltou em reembolso.
#
# A conta e por gasto, e nao por soma solta, porque o `LEAST` precisa de um teto:
# amigo que devolve mais do que a conta nao esta reembolsando, esta pagando outra
# coisa - e abater o excedente faria o mes parecer mais barato do que foi.
#
# E o recorte e pela data do GASTO, nao do reembolso: a pergunta que o Resumo
# responde e "quanto este mes custou para a casa", e o jantar de marco custou o
# que custou mesmo que os amigos so tenham devolvido em abril.
#
# O filtro de "so eu" tambem se ancora no gasto, pelo mesmo motivo: o que esta
# sendo medido e o consumo de quem pagou. Se ele paga o jantar e o dinheiro cai
# na conta da Clarissa, o jantar dele custou menos - exigir que as duas pontas
# fossem da mesma pessoa esconderia o desconto de quem gastou.
_REEMBOLSOS_APLICADOS = f"""
    WITH gasto_do_mes AS (
        SELECT t.id, t.amount
          FROM transactions t
          LEFT JOIN categories c ON c.id = t.category_id
         WHERE t.family_id = :family_id
           AND t.direction = 'SAIDA'
           AND t.status IN ('EFETIVADA', 'CONCILIADA')
           AND COALESCE(c.counts_as_expense, true)
           AND date_trunc('month', t.paid_on)
               = date_trunc('month', CAST(:month AS date))
           {_SCOPE_FILTER}
    ),
    voltou AS (
        SELECT r.reembolso_de_id AS gasto, SUM(r.amount) AS valor
          FROM transactions r
         WHERE r.family_id = :family_id
           AND r.direction = 'ENTRADA'
           AND r.status IN ('EFETIVADA', 'CONCILIADA')
           AND r.reembolso_de_id IS NOT NULL
         GROUP BY 1
    )
    SELECT COALESCE(SUM(LEAST(v.valor, g.amount)), 0)
      FROM gasto_do_mes g
      JOIN voltou v ON v.gasto = g.id
"""


def monthly_cashflow(
    db: Session, family_id: UUID, month: date, member_id: UUID | None
) -> dict:
    """O mes em numeros, com as entradas separadas por natureza.

    Tres baldes de entrada, e nao um:

      * `renda` - o que e renda da familia;
      * `doacoes` - doacao recebida, reconhecida pelo CAMINHO da categoria
        (`receitas.doacoes`), e nao por "nao e renda". Os dois nao sao a mesma
        coisa: o credito do pagamento da fatura tambem nao e renda, e chama-lo
        de doacao seria dizer que os sogros pagaram o cartao;
      * `outras_entradas` - o resto que entrou e nao e renda: transferencia
        entre contas proprias, devolucao, emprestimo.

    E o CARTAO fica fora dos tres. O OFX da fatura traz o pagamento dela como
    credito: numa conta de cartao, dinheiro que "entra" ou paga a divida ou
    cancela uma compra - nenhum dos dois e dinheiro entrando na familia. Por
    isso a regra aqui e estrutural (pelo tipo da conta) e nao depende de a linha
    estar classificada: classificacao erra, tipo de conta nao.
    """
    row = db.execute(
        text(
            f"""
            SELECT
              COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'ENTRADA'), 0) AS inflow,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'ENTRADA'
                    AND COALESCE(c.counts_as_income, true)), 0)                 AS renda,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'ENTRADA'
                    AND c.path <@ 'receitas.doacoes'::ltree), 0)                AS doacoes,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'ENTRADA'
                    AND c.path <@ 'receitas.reembolsos'::ltree), 0)             AS reembolsos,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'ENTRADA'
                    AND COALESCE(c.counts_as_income, true) = false
                    AND NOT COALESCE(c.path <@ 'receitas.doacoes'::ltree, false)
                    AND NOT COALESCE(c.path <@ 'receitas.reembolsos'::ltree, false)), 0)
                                                                                AS outras_entradas,
              COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'SAIDA'),   0) AS outflow,
              -- O que de fato SAIU do bolso da familia, sem o dinheiro que so
              -- mudou de lugar. A linha de pagamento da fatura e o caso que
              -- obriga: a compra do cartao ja esta contada como gasto, e a
              -- fatura que a paga e a MESMA despesa saindo da conta corrente.
              -- Somar as duas - e e isso que `outflow` faz - conta o cartao
              -- inteiro duas vezes, e desde que o mes passou a ser o do caixa
              -- as duas caem no mesmo mes.
              --
              -- Amortizacao e aporte CONTINUAM aqui: o dinheiro saiu mesmo,
              -- e deixou de estar disponivel. Eles nao sao consumo, mas sao
              -- saida.
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'SAIDA'
                    AND NOT COALESCE(c.path <@ 'transferencias'::ltree, false)), 0)
                                                                                AS saiu_do_bolso,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'ENTRADA'
                    AND NOT COALESCE(c.path <@ 'transferencias'::ltree, false)), 0)
                                                                                AS entrou_no_bolso,
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'SAIDA'
                    AND COALESCE(c.counts_as_expense, true) = false), 0)        AS patrimonio,
              -- Quanto do consumo deste mes veio da FATURA do cartao: compras
              -- feitas antes, que so agora sairam da conta. Nao soma em nada - e
              -- uma parte do `consumo`, e existe para a tela poder explicar por
              -- que o mes tem um gasto que ele nao fez neste mes.
              COALESCE(SUM(t.amount) FILTER (
                  WHERE t.direction = 'SAIDA'
                    AND a.type = 'CARTAO_CREDITO'
                    AND COALESCE(c.counts_as_expense, true)), 0)                AS gasto_no_cartao
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
              JOIN accounts a ON a.id = t.account_id
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               -- credito em conta de cartao nao e dinheiro entrando na familia
               AND NOT (t.direction = 'ENTRADA' AND a.type = 'CARTAO_CREDITO')
               AND date_trunc('month', t.paid_on) = date_trunc('month', CAST(:month AS date))
               {_SCOPE_FILTER}
            """
        ),
        {"family_id": family_id, "month": month, "member_id": member_id},
    ).mappings().one()

    # O que foi creditado no cartao no mes, em linha separada. Nao soma em nada:
    # esta aqui para o numero existir em algum lugar, em vez de o lancamento
    # parecer ter sido engolido.
    credito_no_cartao = brl(
        db.execute(
            text(
                f"""
                SELECT COALESCE(SUM(t.amount), 0)
                  FROM transactions t
                  JOIN accounts a ON a.id = t.account_id
                 WHERE t.family_id = :family_id
                   AND t.direction = 'ENTRADA'
                   AND a.type = 'CARTAO_CREDITO'
                   AND t.status IN ('EFETIVADA', 'CONCILIADA')
                   AND date_trunc('month', t.paid_on)
                       = date_trunc('month', CAST(:month AS date))
                   {_SCOPE_FILTER}
                """
            ),
            {"family_id": family_id, "month": month, "member_id": member_id},
        ).scalar()
    )

    aplicadas = brl(
        db.execute(
            text(_DOACOES_APLICADAS),
            {"family_id": family_id, "month": month, "member_id": member_id},
        ).scalar()
    )
    devolvido = brl(
        db.execute(
            text(_REEMBOLSOS_APLICADOS),
            {"family_id": family_id, "month": month, "member_id": member_id},
        ).scalar()
    )

    inflow, outflow = brl(row["inflow"]), brl(row["outflow"])
    # Amortizacao e aporte saem da conta, mas nao sao consumo: sao divida
    # virando patrimonio e dinheiro mudando de bolso. Somados ao gasto, fariam
    # o mes parecer pior - e a taxa de poupanca, menor - justamente para quem
    # esta construindo patrimonio.
    patrimonio = brl(row["patrimonio"])
    consumo = brl(outflow - patrimonio)

    # Entrou na conta, mas nao e renda da familia: doacao recebida. Contar como
    # renda inflaria o mes, a taxa de poupanca e a projecao dos proximos meses -
    # esta ultima e a pior, porque passaria a contar com dinheiro que depende da
    # vontade de outra pessoa.
    renda = brl(row["renda"])
    doacoes = brl(row["doacoes"])
    outras_entradas = brl(row["outras_entradas"])

    # E o outro lado da mesma honestidade: a escola paga pelos avos saiu da conta,
    # mas nao foi a familia que a pagou. Tirar a doacao da renda sem tirar o gasto
    # que ela cobriu seria trocar um erro por outro, e o novo seria pior, porque
    # faria a familia parecer gastadora todo mes.
    # O reembolso entra aqui pelo mesmo motivo que a doacao: o dinheiro saiu da
    # conta, mas nao ficou. A diferenca e de quem era - doacao e dinheiro que
    # chega de outra pessoa, reembolso e dinheiro dele que volta - e por isso os
    # dois tem balde proprio em vez de um "nao e renda" so.
    consumo_proprio = brl(consumo - aplicadas - devolvido)
    savings_rate = (renda - consumo_proprio) / renda if renda else ZERO

    return {
        "month": month.replace(day=1),
        "inflow": inflow,
        "renda": renda,
        "doacoes": doacoes,
        "outras_entradas": outras_entradas,
        "credito_no_cartao": credito_no_cartao,
        "doacoes_aplicadas": aplicadas,
        # parte do `consumo`: a fatura do cartao que venceu neste mes
        "gasto_no_cartao": brl(row["gasto_no_cartao"]),
        "reembolsos": brl(row["reembolsos"]),
        "reembolsos_aplicados": devolvido,
        "outflow": outflow,
        # o que saiu e o que entrou de verdade, sem o dinheiro que so mudou de
        # lugar (pagamento de fatura, transferencia entre contas proprias)
        "saiu_do_bolso": brl(row["saiu_do_bolso"]),
        "entrou_no_bolso": brl(row["entrou_no_bolso"]),
        "consumo": consumo,
        "consumo_proprio": consumo_proprio,
        "patrimonio": patrimonio,
        # "sobrou no mes". Fora as transferencias dos dois lados: a fatura paga
        # e a mesma despesa que as compras dela, e somar as duas fazia o mes
        # parecer o dobro de caro - agora que compra e fatura caem no mesmo mes,
        # todo mes com cartao estaria errado.
        "net": brl(brl(row["entrou_no_bolso"]) - brl(row["saiu_do_bolso"])),
        "savings_rate": Decimal(savings_rate).quantize(Decimal("0.0001")),
    }


def year_calendar(
    db: Session, family_id: UUID, year: int, member_id: UUID | None
) -> list[dict]:
    """Quanto entrou e quanto saiu em cada mes do ano.

    "Uma tela com 12 retangulos com as abreviacoes de cada mes mostrando ali
    quanto entrou e o quanto saiu em cada mes."

    Os dois numeros sao os mesmos do Resumo - `entrou_no_bolso` e
    `saiu_do_bolso` -, e nao o extrato bruto. Transferencia entre contas
    proprias e pagamento de fatura ficam de fora dos dois lados: a fatura e a
    mesma despesa que as compras dela, e soma-las faria o ano inteiro parecer o
    dobro do que foi.

    Os doze meses vem sempre, inclusive os vazios e os que ainda nao
    aconteceram. Um calendario com buracos obriga quem le a contar nos dedos
    qual mes e qual.
    """
    linhas = db.execute(
        text(
            f"""
            SELECT date_trunc('month', t.paid_on)::date AS mes,
                   COALESCE(SUM(t.amount) FILTER (
                       WHERE t.direction = 'ENTRADA'
                         AND NOT COALESCE(c.path <@ 'transferencias'::ltree, false)
                   ), 0) AS entrou,
                   COALESCE(SUM(t.amount) FILTER (
                       WHERE t.direction = 'SAIDA'
                         AND NOT COALESCE(c.path <@ 'transferencias'::ltree, false)
                   ), 0) AS saiu
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
              JOIN accounts a ON a.id = t.account_id
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               -- credito em conta de cartao nao e dinheiro entrando na familia
               AND NOT (t.direction = 'ENTRADA' AND a.type = 'CARTAO_CREDITO')
               AND EXTRACT(YEAR FROM t.paid_on) = :ano
               {_SCOPE_FILTER}
             GROUP BY 1
            """
        ),
        {"family_id": family_id, "ano": year, "member_id": member_id},
    ).mappings().all()

    por_mes = {linha["mes"]: linha for linha in linhas}
    calendario = []
    for mes in range(1, 13):
        primeiro = date(year, mes, 1)
        linha = por_mes.get(primeiro)
        entrou = brl(linha["entrou"]) if linha else ZERO
        saiu = brl(linha["saiu"]) if linha else ZERO
        calendario.append(
            {
                "month": primeiro,
                "entrou": entrou,
                "saiu": saiu,
                "net": brl(entrou - saiu),
            }
        )
    return calendario


def gasto_medio_mensal(
    db: Session,
    family_id: UUID,
    member_id: UUID | None,
    *,
    ate: date,
    janela: int = 12,
) -> dict:
    """Quanto custa um mes tipico.

    "Retire aquele 'fatura em aberto', sempre que mando a fatura aqui ela ja
    esta paga. Pode substituir por um 'Gasto medio mensal'."

    O numero medido e EXATAMENTE o mesmo da linha "Gastos de <mes>", que fica
    coladinha nela na tela: as duas se chamam gasto, aparecem uma embaixo da
    outra, e vao ser comparadas uma com a outra - se cada uma contasse uma
    coisa (uma com aporte de investimento dentro, a outra sem), a comparacao
    mentiria sem nunca parecer errada. Por isso aqui se roda o mesmo calculo do
    mes, mes a mes, em vez de uma soma propria parecida.

    Duas regras sobre quais meses entram:

      * o mes corrente fica DE FORA (a janela termina no ultimo mes fechado).
        No dia 3 ele tem tres dias de gasto, e entraria puxando a media para
        baixo todo comeco de mes - o numero cairia sozinho sem ninguem ter
        gastado menos;

      * mes sem gasto nenhum nao conta no divisor. Dividir por doze quem tem
        tres meses de sistema daria um quarto do gasto real, e o numero mais
        perigoso aqui e o que aparece baixo demais: e por ele que se decide que
        da para gastar.
    """
    primeiro = ate.replace(day=1)
    meses_olhados = [meses_depois(primeiro, -passo) for passo in range(janela)]

    gastos = []
    for mes in meses_olhados:
        gasto = monthly_cashflow(db, family_id, mes, member_id)["consumo_proprio"]
        if gasto > ZERO:
            gastos.append((mes, gasto))

    total = sum((gasto for _, gasto in gastos), ZERO)
    meses = len(gastos)
    return {
        "media": brl(total / meses) if meses else ZERO,
        "meses": meses,
        "total": brl(total),
        # o mes mais antigo que entrou na conta, para a tela poder dizer
        # "nos ultimos 7 meses" em vez de prometer doze que nao existem
        "desde": min((mes for mes, _ in gastos), default=None),
        "ate": primeiro,
    }


def sankey_rows(db: Session, family_id: UUID, month: date, member_id: UUID | None) -> list[FlowRow]:
    """Fluxos do mes ja resolvidos ate o nivel 2 (grupo) e o nivel exibido."""
    rows = db.execute(
        text(
            f"""
            SELECT t.direction::text AS direction,
                   COALESCE(grp.name, 'Sem categoria')  AS grp,
                   COALESCE(c.name,   'Sem categoria')  AS category,
                   SUM(t.amount)                        AS amount
              FROM transactions t
              LEFT JOIN categories c   ON c.id = t.category_id
              LEFT JOIN categories grp ON grp.family_id IS NOT DISTINCT FROM c.family_id
                                      AND grp.path = subpath(c.path, 0, LEAST(2, nlevel(c.path)))
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               AND date_trunc('month', t.paid_on) = date_trunc('month', CAST(:month AS date))
               {_SCOPE_FILTER}
             GROUP BY 1, 2, 3
            """
        ),
        {"family_id": family_id, "month": month, "member_id": member_id},
    ).mappings().all()

    return [
        FlowRow(
            direction=r["direction"],
            group=r["grp"],
            category=r["category"],
            amount=brl(r["amount"]),
        )
        for r in rows
    ]


def spend_by_budget_cap(db: Session, family_id: UUID, month: date) -> list[dict]:
    """Gasto realizado no mes para cada teto configurado.

    `includes_descendants` faz a soma descer a subarvore inteira via ltree.
    """
    rows = db.execute(
        text(
            """
            SELECT b.id            AS cap_id,
                   b.category_id,
                   c.name          AS category_name,
                   b.member_id,
                   b.amount        AS cap,
                   b.alert_at_pct,
                   COALESCE((
                       SELECT SUM(t.amount)
                         FROM transactions t
                         JOIN categories tc ON tc.id = t.category_id
                        WHERE t.family_id = b.family_id
                          AND t.direction = 'SAIDA'
                          AND t.status IN ('EFETIVADA', 'CONCILIADA')
                          AND date_trunc('month', t.paid_on)
                              = date_trunc('month', CAST(:month AS date))
                          AND (b.member_id IS NULL OR t.owner_member_id = b.member_id)
                          AND (CASE WHEN b.includes_descendants
                                    THEN tc.path <@ c.path
                                    ELSE tc.id = c.id END)
                   ), 0) AS spent
              FROM budget_caps b
              JOIN categories c ON c.id = b.category_id
             WHERE b.family_id = :family_id
               AND b.starts_on <= CAST(:month AS date)
               AND (b.ends_on IS NULL OR b.ends_on >= CAST(:month AS date))
            """
        ),
        {"family_id": family_id, "month": month},
    ).mappings().all()
    return [dict(r) for r in rows]


def ir_year_rows(db: Session, family_id: UUID, member_id: UUID, year: int) -> dict:
    """Materializa rendimentos e despesas dedutiveis do ano para o motor de IR.

    A classificacao sai da view `v_transactions_ir`, que ja resolve
    'override da transacao > herdado da categoria'.
    """
    incomes = db.execute(
        text(
            """
            SELECT v.ir_treatment::text AS treatment, SUM(v.amount) AS amount
              FROM v_transactions_ir v
             WHERE v.family_id = :family_id
               AND v.owner_member_id = :member_id
               AND v.ir_year = :year
               AND v.direction = 'ENTRADA'
             GROUP BY 1
            """
        ),
        {"family_id": family_id, "member_id": member_id, "year": year},
    ).mappings().all()

    deductions = db.execute(
        text(
            """
            SELECT v.ir_deduction_type::text AS deduction_type,
                   v.ir_deduction_member_id  AS member_id,
                   m.full_name               AS member_name,
                   SUM(v.amount)             AS amount
              FROM v_transactions_ir v
              LEFT JOIN members m ON m.id = v.ir_deduction_member_id
             WHERE v.family_id = :family_id
               AND v.owner_member_id = :member_id
               AND v.ir_year = :year
               AND v.direction = 'SAIDA'
               AND v.ir_deduction_type <> 'NENHUMA'
             GROUP BY 1, 2, 3
            """
        ),
        {"family_id": family_id, "member_id": member_id, "year": year},
    ).mappings().all()

    dependents = db.execute(
        text(
            """
            SELECT COUNT(*) AS n
              FROM members
             WHERE family_id = :family_id
               AND is_ir_dependent
               AND (ir_dependent_of = :member_id OR ir_dependent_of IS NULL)
            """
        ),
        {"family_id": family_id, "member_id": member_id},
    ).scalar_one()

    return {
        "incomes": [dict(r) for r in incomes],
        "deductions": [
            {**dict(r), "member_name": nome_curto(r["member_name"])}
            for r in deductions
        ],
        "dependents": int(dependents or 0),
    }


def spend_by_category(
    db: Session,
    family_id: UUID,
    start: date,
    end: date,
    member_id: UUID | None,
    depth: int = 2,
) -> list[dict]:
    """Gastos agrupados pelo nivel `depth` da arvore de categorias.

    `depth=1` agrega em Essenciais / Estilo de Vida / Metas / Financeiro;
    `depth=2` desce para Moradia, Alimentacao, Saude...; e assim por diante.
    O corte usa `subpath` do ltree, entao continua valendo se a arvore mudar de
    formato - inclusive quando o Felipe trocar a taxonomia pela dele.

    Lancamentos sem categoria nao somem: aparecem agrupados em 'Sem categoria',
    que e justamente o que precisa de atencao.
    """
    rows = db.execute(
        text(
            f"""
            WITH gastos AS (
                SELECT t.id,
                       t.amount,
                       t.owner_member_id,
                       CASE WHEN c.id IS NULL THEN NULL
                            ELSE subpath(c.path, 0, LEAST(:depth, nlevel(c.path)))
                       END AS grupo_path
                  FROM transactions t
                  LEFT JOIN categories c ON c.id = t.category_id
                 WHERE t.family_id = :family_id
                   AND t.direction = 'SAIDA'
                   AND t.status IN ('EFETIVADA', 'CONCILIADA')
                   AND t.paid_on BETWEEN :start AND :end
                   -- amortizacao e aporte saem da conta, mas nao sao consumo
                   AND COALESCE(c.counts_as_expense, true)
                   {_SCOPE_FILTER}
            )
            SELECT COALESCE(g.grupo_path::text, 'sem_categoria') AS path,
                   COALESCE(cat.name, 'Sem categoria')           AS name,
                   COALESCE(cat.icon, NULL)                      AS icon,
                   SUM(g.amount)                                 AS total,
                   COUNT(*)                                      AS lancamentos
              FROM gastos g
              LEFT JOIN categories cat
                     ON cat.path = g.grupo_path
                    AND cat.family_id IS NOT DISTINCT FROM :family_id
             GROUP BY 1, 2, 3
             ORDER BY 4 DESC
            """
        ),
        {
            "family_id": family_id,
            "start": start,
            "end": end,
            "member_id": member_id,
            "depth": depth,
        },
    ).mappings().all()

    total = sum((Decimal(r["total"]) for r in rows), ZERO)
    return [
        {
            "path": r["path"],
            "name": r["name"],
            "icon": r["icon"],
            "total": brl(r["total"]),
            "transactions": int(r["lancamentos"]),
            "share": (
                (Decimal(r["total"]) / total).quantize(Decimal("0.0001"))
                if total
                else ZERO
            ),
        }
        for r in rows
    ]


def spend_by_member(
    db: Session, family_id: UUID, start: date, end: date
) -> list[dict]:
    """Quanto cada um gastou no periodo - a leitura que so faz sentido depois
    de o responsavel poder ser informado por lancamento."""
    rows = db.execute(
        text(
            """
            SELECT m.id, m.full_name, COALESCE(m.nickname, m.full_name) AS apelido,
                   COALESCE(SUM(t.amount), 0) AS total,
                   COUNT(t.id)                AS lancamentos
              FROM members m
              LEFT JOIN transactions t
                     ON t.owner_member_id = m.id
                    AND t.direction = 'SAIDA'
                    AND t.status IN ('EFETIVADA', 'CONCILIADA')
                    AND t.paid_on BETWEEN :start AND :end
             WHERE m.family_id = :family_id
               AND m.password_hash IS NOT NULL
             GROUP BY 1, 2, 3
             ORDER BY 4 DESC
            """
        ),
        {"family_id": family_id, "start": start, "end": end},
    ).mappings().all()

    total = sum((Decimal(r["total"]) for r in rows), ZERO)
    return [
        {
            "member_id": r["id"],
            # Nome curto, nao completo: o que a API manda e o que fica
            # gravado no celular no modo offline. Ver app/services/mascara.py.
            "name": nome_curto(r["apelido"]),
            "total": brl(r["total"]),
            "transactions": int(r["lancamentos"]),
            "share": (
                (Decimal(r["total"]) / total).quantize(Decimal("0.0001"))
                if total
                else ZERO
            ),
        }
        for r in rows
    ]


def note_required_for(db: Session, category_id: UUID) -> str | None:
    """Nome da categoria que exige comentario, olhando a subarvore inteira.

    A exigencia e herdada: marcar 'Unicos' vale para 'Unicos > Viagens' e para
    qualquer filha criada depois. Sem a heranca, bastaria criar uma subcategoria
    para escapar da regra - e a exigencia existe justamente para o gasto avulso,
    que e onde os filhos ficam.
    """
    return db.execute(
        text(
            """
            SELECT ancestral.name
              FROM categories alvo
              JOIN categories ancestral
                ON ancestral.family_id IS NOT DISTINCT FROM alvo.family_id
               AND alvo.path <@ ancestral.path
             WHERE alvo.id = :category_id
               AND ancestral.requires_note
             ORDER BY nlevel(ancestral.path)
             LIMIT 1
            """
        ),
        {"category_id": category_id},
    ).scalar_one_or_none()


def pendentes_de_categoria(
    db: Session, family_id: UUID, month: date, member_id: UUID | None
) -> dict:
    """Quanto do mes ainda esta em "A definir", e quantos lancamentos sao.

    Existe para o painel poder cobrar. "Salvo agora, arrumo depois" so funciona
    se o depois aparecer em algum lugar - sem isto, o lancamento que ninguem
    classificou fica num canto da lista de categorias e sobrevive ao mes.

    Conta tambem a categoria nula, que e a forma antiga do mesmo problema.
    """
    row = db.execute(
        text(
            f"""
            SELECT COUNT(*)                   AS quantos,
                   COALESCE(SUM(t.amount), 0) AS total
              FROM transactions t
              LEFT JOIN categories c ON c.id = t.category_id
             WHERE t.family_id = :family_id
               AND t.status IN ('EFETIVADA', 'CONCILIADA')
               AND t.direction <> 'TRANSFERENCIA'
               AND (t.category_id IS NULL OR c.slug = 'a_definir')
               AND date_trunc('month', t.paid_on)
                   = date_trunc('month', CAST(:month AS date))
               {_SCOPE_FILTER}
            """
        ),
        {"family_id": family_id, "month": month, "member_id": member_id},
    ).mappings().one()
    return {"quantos": int(row["quantos"]), "total": brl(row["total"])}
