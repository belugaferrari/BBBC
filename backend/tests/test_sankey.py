"""O Sankey do dashboard tem que fechar: o que entra e igual ao que sai."""

from decimal import Decimal

from app.services.sankey import CENTRAL_NODE, SURPLUS_NODE, FlowRow, build_sankey


def rows() -> list[FlowRow]:
    return [
        FlowRow("ENTRADA", "Ativa Fixa", "Pro-labore", Decimal("28000")),
        FlowRow("ENTRADA", "Ativa Variavel", "Distribuicao de lucros", Decimal("15000")),
        FlowRow("ENTRADA", "Passiva", "Rendimentos de FII", Decimal("1200")),
        FlowRow("SAIDA", "Essenciais", "Supermercado", Decimal("4200")),
        FlowRow("SAIDA", "Essenciais", "Mensalidade escolar", Decimal("6800")),
        FlowRow("SAIDA", "Essenciais", "Plano de saude", Decimal("2400")),
        FlowRow("SAIDA", "Essenciais", "Gas", Decimal("150")),
        FlowRow("SAIDA", "Estilo de Vida", "Restaurantes", Decimal("2100")),
        FlowRow("SAIDA", "Estilo de Vida", "Impressao 3D (Bambu Lab)", Decimal("900")),
        FlowRow("SAIDA", "Metas & Projetos", "Fundo viagem Disney", Decimal("3000")),
    ]


def test_totais_e_saldo():
    grafico = build_sankey(rows())
    assert grafico["total_income"] == Decimal("44200.00")
    assert grafico["total_expense"] == Decimal("19550.00")
    assert grafico["balance"] == Decimal("24650.00")


def test_soma_dos_links_que_saem_do_no_central_e_a_receita_total():
    grafico = build_sankey(rows())
    saidas = sum(
        (link["value"] for link in grafico["links"] if link["source"] == CENTRAL_NODE),
        Decimal("0"),
    )
    assert saidas == grafico["total_income"]


def test_sobra_do_mes_vira_no_proprio():
    grafico = build_sankey(rows())
    assert any(node["id"] == SURPLUS_NODE for node in grafico["nodes"])


def test_deficit_entra_como_uso_de_reservas():
    grafico = build_sankey(
        [
            FlowRow("ENTRADA", "Ativa Fixa", "Pro-labore", Decimal("5000")),
            FlowRow("SAIDA", "Essenciais", "Aluguel", Decimal("8000")),
        ]
    )
    assert grafico["balance"] == Decimal("-3000.00")
    assert any(link["target"] == CENTRAL_NODE and link["value"] == Decimal("3000.00")
               for link in grafico["links"])


def test_categorias_irrelevantes_viram_outros():
    grafico = build_sankey(rows())
    folhas = [n["label"] for n in grafico["nodes"] if n["stage"] == 3]
    assert "Outros" in folhas          # 'Gas' (150) fica abaixo de 1% do total
    assert "Supermercado" in folhas
