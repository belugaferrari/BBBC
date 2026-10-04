"""Dinheiro que entra e nao e renda.

"Meu sogro e minha sogra depositam dinheiro para pagar a escola das meninas todo
mes. Mas isso e complexo: nao faz parte da nossa renda mensal."

Sao duas honestidades, e uma sozinha mente mais que nenhuma:

  * a doacao nao e renda da familia - contar como renda infla o mes, a taxa de
    poupanca e, pior, a projecao, que passaria a contar com dinheiro que depende
    da vontade de outra pessoa;

  * mas a escola que ela pagou tambem nao e gasto da familia - tirar a entrada
    sem tirar a saida faria a casa parecer gastadora todo mes.

O imposto aqui sao dois, e confundi-los e o erro comum: no IMPOSTO DE RENDA
(federal) a doacao recebida e isenta e vai para "Rendimentos Isentos e Nao
Tributaveis"; o limite de isencao de que ele se lembrava e do ITCMD, que e
ESTADUAL - muda de estado para estado e e corrigido todo ano. Por isso o limite
nasce vazio e o resumo avisa, em vez de chutar um numero que tranquilizaria sobre
um limite que nao e o desta familia.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("BBBC_TEST_DATABASE_URL"),
    reason="defina BBBC_TEST_DATABASE_URL para rodar a integracao",
)

MES = "2026-03-01"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def casa(client):
    """Familia nova a cada teste: doador e limite sao estado, e estado vaza."""
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.doa.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe Ferrari",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa Ferrari",
        conjuge_email=f"clarissa.doa.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=["Cecilia Ferrari", "Giovanna Ferrari"],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    conta = client.post(
        "/api/v1/accounts",
        json={"name": "Conta", "type": "CONTA_CORRENTE"},
        headers=headers,
    ).json()
    with SessionLocal() as db:
        cats = {
            linha[0]: str(linha[1])
            for linha in db.execute(
                text("SELECT path::text, id FROM categories WHERE family_id = :f"),
                {"f": family_id},
            )
        }
        # Uma receita que E renda, escolhida do proprio catalogo: o teste nao deve
        # depender do nome da categoria de trabalho, que pode mudar.
        renda = db.execute(
            text(
                """
                SELECT path::text FROM categories
                 WHERE family_id = :f AND kind = 'RECEITA' AND counts_as_income
                   AND nlevel(path) > 1
                 ORDER BY sort_order LIMIT 1
                """
            ),
            {"f": family_id},
        ).scalar_one()
    return {
        "family_id": family_id,
        "headers": headers,
        "conta": conta["id"],
        "cat": cats,
        "renda": renda,
    }


def lancar(
    client,
    casa,
    *,
    direction: str,
    amount: str,
    categoria: str,
    descricao: str = "Lancamento",
    dia: str = MES,
    donor_id: str | None = None,
    destino: str | None = None,
    notes: str | None = None,
):
    corpo = {
        "account_id": casa["conta"],
        "direction": direction,
        "amount": amount,
        "booked_on": dia,
        "description": descricao,
        "category_id": casa["cat"][categoria],
        "status": "EFETIVADA",
    }
    if donor_id:
        corpo["donor_id"] = donor_id
    if destino:
        corpo["donation_for_category_id"] = casa["cat"][destino]
    if notes:
        corpo["notes"] = notes
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def doador(client, casa, nome: str, parentesco: str | None = None):
    resposta = client.post(
        "/api/v1/donors",
        json={"name": nome, "relationship": parentesco},
        headers=casa["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def resumo_do_mes(client, casa, mes: str = MES) -> dict:
    resposta = client.get(
        "/api/v1/dashboard", params={"month": mes}, headers=casa["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["cashflow"]


# ---------------------------------------------------------------------------
# A doacao nao e renda
# ---------------------------------------------------------------------------
def test_familia_nova_nasce_com_a_doacao_fora_da_renda(client, casa):
    """A marca tem de atravessar a copia do catalogo.

    O catalogo global diz `counts_as_income = false` na doacao, mas a familia usa
    uma COPIA dele. A copia que esquecesse esta coluna pegaria o DEFAULT da
    tabela, que e true - e a doacao voltaria a ser renda em silencio, sem erro
    nenhum na tela. Foi exatamente o que aconteceu na primeira versao.
    """
    from sqlalchemy import text

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        marcas = dict(
            db.execute(
                text(
                    """
                    SELECT path::text, counts_as_income
                      FROM categories
                     WHERE family_id = :f AND path <@ 'receitas.doacoes'::ltree
                    """
                ),
                {"f": casa["family_id"]},
            ).all()
        )
    assert marcas, "a familia nova precisa ter a arvore de doacoes"
    assert set(marcas.values()) == {False}


def test_a_arvore_que_o_aplicativo_recebe_diz_qual_categoria_e_doacao(client, casa):
    """Sem a coluna na resposta, a tela de lancamento nunca pediria o doador.

    A arvore e montada campo a campo no servidor, e uma coluna nova que nao entre
    nessa montagem chega ao aplicativo com o DEFAULT do schema - true. A tela
    trataria o deposito dos avos como salario, sem erro nenhum para desconfiar.
    """
    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()
    achatada: dict[str, dict] = {}

    def andar(nos: list[dict]) -> None:
        for no in nos:
            achatada[no["path"]] = no
            andar(no["children"])

    andar(arvore)
    assert achatada["receitas.doacoes"]["counts_as_income"] is False
    assert achatada["receitas.doacoes.familiares"]["counts_as_income"] is False
    # e a receita de verdade continua sendo renda. O reembolso fica de fora da
    # conferencia porque ele TAMBEM nao e renda - e dinheiro dele que volta, nao
    # dinheiro de outra pessoa que chega. Sao dois baldes de propósito: no balde
    # da doacao, o reembolso do jantar apareceria como doacao de alguem, e o
    # limite de isencao do ITCMD passaria a contar dinheiro que nunca foi doado.
    renda = [
        no
        for caminho, no in achatada.items()
        if no["kind"] == "RECEITA"
        and not caminho.startswith("receitas.doacoes")
        and not caminho.startswith("receitas.reembolsos")
    ]
    assert renda and all(no["counts_as_income"] for no in renda)



def test_doacao_entra_na_conta_mas_nao_na_renda(client, casa):
    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancar(
        client, casa, direction="ENTRADA", amount="28000.00",
        categoria=casa["renda"], descricao="Pro-labore",
    )
    lancar(
        client, casa, direction="ENTRADA", amount="2000.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito V",
        donor_id=vera["id"], destino="despesas.educacao",
    )

    fluxo = resumo_do_mes(client, casa)
    # entrou na conta: os dois
    assert Decimal(fluxo["inflow"]) == Decimal("30000.00")
    # renda da familia: so o pro-labore
    assert Decimal(fluxo["renda"]) == Decimal("28000.00")
    assert Decimal(fluxo["doacoes"]) == Decimal("2000.00")


def test_doacao_abate_do_consumo_so_o_que_cobriu(client, casa):
    """A escola paga pelos avos nao e gasto da casa - mas so ate o que se gastou."""
    jose = doador(client, casa, "Jose Sogro", "sogro")
    lancar(
        client, casa, direction="ENTRADA", amount="28000.00",
        categoria=casa["renda"], descricao="Pro-labore",
    )
    lancar(
        client, casa, direction="ENTRADA", amount="3500.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        donor_id=jose["id"], destino="despesas.educacao",
    )
    lancar(
        client, casa, direction="SAIDA", amount="3200.00",
        categoria="despesas.educacao", descricao="Escola",
    )
    lancar(
        client, casa, direction="SAIDA", amount="1800.00",
        categoria="despesas.mercado", descricao="Mercado",
    )

    fluxo = resumo_do_mes(client, casa)
    assert Decimal(fluxo["consumo"]) == Decimal("5000.00")
    # 3.500 doados, 3.200 de escola: abate 3.200, nao 3.500
    assert Decimal(fluxo["doacoes_aplicadas"]) == Decimal("3200.00")
    assert Decimal(fluxo["consumo_proprio"]) == Decimal("1800.00")


def test_doacao_sem_gasto_no_destino_nao_abate_nada(client, casa):
    """Doacao guardada para a escola do mes que vem nao melhora este mes."""
    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancar(
        client, casa, direction="ENTRADA", amount="10000.00",
        categoria=casa["renda"], descricao="Pro-labore",
    )
    lancar(
        client, casa, direction="ENTRADA", amount="3500.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        donor_id=vera["id"], destino="despesas.educacao",
    )
    lancar(
        client, casa, direction="SAIDA", amount="1800.00",
        categoria="despesas.mercado", descricao="Mercado",
    )

    fluxo = resumo_do_mes(client, casa)
    assert Decimal(fluxo["doacoes_aplicadas"]) == Decimal("0.00")
    assert Decimal(fluxo["consumo_proprio"]) == Decimal("1800.00")


def test_taxa_de_poupanca_nao_infla_com_doacao(client, casa):
    """O numero que a doacao estragaria mais: 30.000 de 'renda' com 1.800 de
    gasto daria 94%; a verdade e 28.000 com 1.800."""
    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancar(
        client, casa, direction="ENTRADA", amount="28000.00",
        categoria=casa["renda"], descricao="Pro-labore",
    )
    lancar(
        client, casa, direction="ENTRADA", amount="2000.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        donor_id=vera["id"], destino="despesas.educacao",
    )
    lancar(
        client, casa, direction="SAIDA", amount="2000.00",
        categoria="despesas.educacao", descricao="Escola",
    )
    lancar(
        client, casa, direction="SAIDA", amount="1800.00",
        categoria="despesas.mercado", descricao="Mercado",
    )

    fluxo = resumo_do_mes(client, casa)
    esperada = (Decimal("28000") - Decimal("1800")) / Decimal("28000")
    assert Decimal(fluxo["savings_rate"]) == esperada.quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# O resumo por doador, que e a conta que o ITCMD exige
# ---------------------------------------------------------------------------
def test_resumo_soma_por_doador_e_nao_no_total(client, casa):
    vera = doador(client, casa, "Vera Sogra", "sogra")
    jose = doador(client, casa, "Jose Sogro", "sogro")
    for mes in ("2026-01-10", "2026-02-10", "2026-03-10"):
        lancar(
            client, casa, direction="ENTRADA", amount="2000.00",
            categoria="receitas.doacoes.familiares", descricao="Deposito V",
            dia=mes, donor_id=vera["id"], destino="despesas.educacao",
        )
        lancar(
            client, casa, direction="ENTRADA", amount="1500.00",
            categoria="receitas.doacoes.familiares", descricao="Deposito J",
            dia=mes, donor_id=jose["id"], destino="despesas.educacao",
        )

    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    por_nome = {d["name"]: d for d in resumo["donors"]}
    assert Decimal(por_nome["Vera S."]["total"]) == Decimal("6000.00")
    assert Decimal(por_nome["Jose S."]["total"]) == Decimal("4500.00")
    assert por_nome["Vera S."]["deposits"] == 3
    assert Decimal(resumo["total"]) == Decimal("10500.00")
    # cada um medido separado: somar os dois num balde esconderia de qual se trata
    assert len(resumo["donors"]) == 2


def test_nome_do_doador_sai_abreviado(client, casa):
    """Mesma regra dos nomes da familia: nome completo nao aparece no aplicativo."""
    doador(client, casa, "Vera Lucia Sobrenome Longo", "sogra")
    resumo = client.get("/api/v1/doacoes/resumo", headers=casa["headers"]).json()
    nomes = [d["name"] for d in resumo["donors"]]
    assert "Vera Lucia Sobrenome Longo" not in nomes
    # primeiro nome inteiro, sobrenome em inicial: da para saber quem e sem
    # anunciar o nome completo de quem nem usa o aplicativo
    assert nomes == ["Vera L. S. L."]


def test_resumo_avisa_quando_o_limite_nao_esta_preenchido(client, casa):
    doador(client, casa, "Vera Sogra", "sogra")
    resumo = client.get("/api/v1/doacoes/resumo", headers=casa["headers"]).json()
    assert resumo["itcmd_annual_exemption"] is None
    assert resumo["aviso"] and "estadual" in resumo["aviso"]
    # sem limite nao se inventa percentual de uso
    assert resumo["donors"][0]["used_pct"] is None
    assert resumo["donors"][0]["should_alert"] is False


def test_limite_preenchido_mede_o_uso_e_avisa_perto_do_teto(client, casa):
    vera = doador(client, casa, "Vera Sogra", "sogra")
    client.put(
        "/api/v1/doacoes/limite",
        json={"itcmd_state": "sp", "itcmd_annual_exemption": "10000.00"},
        headers=casa["headers"],
    )
    lancar(
        client, casa, direction="ENTRADA", amount="8500.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        dia="2026-02-10", donor_id=vera["id"],
    )
    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert resumo["itcmd_state"] == "SP"
    assert resumo["aviso"] is None
    linha = resumo["donors"][0]
    assert Decimal(linha["used_pct"]) == Decimal("0.8500")
    assert Decimal(linha["remaining"]) == Decimal("1500.00")
    assert linha["should_alert"] is True


def test_doacao_sem_doador_aparece_como_sem_doador(client, casa):
    """Nao da para medir contra limite nenhum - e dizer isso e melhor que deixar
    a soma por doador parecer completa."""
    lancar(
        client, casa, direction="ENTRADA", amount="1200.00",
        categoria="receitas.doacoes.outras", descricao="Deposito de alguem",
        dia="2026-02-10",
    )
    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert Decimal(resumo["sem_doador"]) == Decimal("1200.00")
    assert Decimal(resumo["total"]) == Decimal("1200.00")
    # e vem a lista, para a tela poder resolver em vez de so reclamar
    assert [l["description"] for l in resumo["sem_doador_lancamentos"]] == [
        "Deposito de alguem"
    ]


def test_descricao_do_extrato_nao_devolve_numero_de_conta(client, casa):
    """O extrato traz agencia e conta na propria descricao do deposito."""
    lancar(
        client, casa, direction="ENTRADA", amount="1200.00",
        categoria="receitas.doacoes.outras",
        descricao="TED RECEBIDA AG 1234 CC 567890",
        dia="2026-02-10",
    )
    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    descricao = resumo["sem_doador_lancamentos"][0]["description"]
    assert "567890" not in descricao
    assert "1234" not in descricao


def test_apontar_o_doador_tira_a_doacao_do_balde_sem_dono(client, casa):
    """O deposito que veio do extrato chega sem doador - o banco nao sabe quem
    depositou. Apontar depois e o caminho normal, nao a excecao."""
    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancamento = lancar(
        client, casa, direction="ENTRADA", amount="2000.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        dia="2026-02-10",
    )
    resposta = client.patch(
        f"/api/v1/transactions/{lancamento['id']}",
        json={"donor_id": vera["id"]},
        headers=casa["headers"],
    )
    assert resposta.status_code == 200, resposta.text

    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert Decimal(resumo["sem_doador"]) == Decimal("0.00")
    assert resumo["sem_doador_lancamentos"] == []
    assert Decimal(resumo["donors"][0]["total"]) == Decimal("2000.00")


def test_doador_arquivado_sai_da_lista_mas_fica_no_ano_em_que_doou(client, casa):
    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancar(
        client, casa, direction="ENTRADA", amount="2000.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        dia="2026-02-10", donor_id=vera["id"],
    )
    assert client.delete(
        f"/api/v1/donors/{vera['id']}", headers=casa["headers"]
    ).status_code == 200

    # fora da lista de escolha
    lista = client.get("/api/v1/donors", headers=casa["headers"]).json()
    assert lista == []
    # mas o dinheiro do ano continua com dono
    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert [d["name"] for d in resumo["donors"]] == ["Vera S."]
    assert resumo["donors"][0]["is_active"] is False
    assert Decimal(resumo["total"]) == Decimal("2000.00")


def test_doador_arquivado_sem_doacao_no_ano_nao_polui_o_resumo(client, casa):
    vera = doador(client, casa, "Vera Sogra", "sogra")
    client.delete(f"/api/v1/donors/{vera['id']}", headers=casa["headers"])
    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    assert resumo["donors"] == []


# ---------------------------------------------------------------------------
# Autorizacao: id de doador de outra familia
# ---------------------------------------------------------------------------
def test_doador_de_outra_familia_nao_serve(client, casa):
    """Autenticar nao e autorizar: o id tem de ser da propria familia."""
    from app.cli import seed_family
    from app.db.session import SessionLocal
    from sqlalchemy import text

    sufixo = uuid.uuid4().hex[:8]
    outra = seed_family(
        name=f"Outra {sufixo}", titular="Outro", titular_email=f"outro.{sufixo}@exemplo.com",
        titular_password="segredo-de-teste", conjuge=None, conjuge_email=None,
        conjuge_password=None, dependentes=[],
    )
    with SessionLocal.begin() as db:
        alheio = db.execute(
            text(
                "INSERT INTO donors (family_id, name) VALUES (:f, 'Alheio') RETURNING id"
            ),
            {"f": outra},
        ).scalar_one()

    resposta = client.post(
        "/api/v1/transactions",
        json={
            "account_id": casa["conta"],
            "direction": "ENTRADA",
            "amount": "1000.00",
            "booked_on": MES,
            "description": "Deposito",
            "category_id": casa["cat"]["receitas.doacoes.familiares"],
            "status": "EFETIVADA",
            "donor_id": str(alheio),
        },
        headers=casa["headers"],
    )
    assert resposta.status_code == 404

    # e nem pelo /donors
    assert client.patch(
        f"/api/v1/donors/{alheio}", json={"name": "Renomeado"}, headers=casa["headers"]
    ).status_code == 404


def test_doacao_e_rendimento_isento_no_ir(client, casa):
    """No imposto de renda (federal) ela nao paga - vai para 'Rendimentos
    Isentos e Nao Tributaveis'. O ITCMD e outro imposto e outra guia."""
    from sqlalchemy import text

    from app.db.session import SessionLocal

    vera = doador(client, casa, "Vera Sogra", "sogra")
    lancar(
        client, casa, direction="ENTRADA", amount="2000.00",
        categoria="receitas.doacoes.familiares", descricao="Deposito",
        dia="2026-02-10", donor_id=vera["id"],
    )
    with SessionLocal() as db:
        tratamento = db.execute(
            text(
                """
                SELECT v.ir_treatment::text
                  FROM v_transactions_ir v
                 WHERE v.family_id = :f
                   AND v.category_path <@ 'receitas.doacoes'::ltree
                """
            ),
            {"f": casa["family_id"]},
        ).scalars().all()
    assert tratamento == ["ISENTO_NAO_TRIBUTAVEL"]
