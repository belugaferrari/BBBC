"""O cartao em dois extratos, e as entradas que nao sao renda.

O cartao e o unico lugar onde o MESMO dinheiro aparece em dois arquivos: a
compra, no extrato do cartao, e o pagamento da fatura, no da conta corrente. A
regra do sistema e que a despesa e a COMPRA, e o pagamento e bolso trocando de
lugar - e ela tem dois jeitos de dar errado, um em cada direcao:

  * CONTAR DUAS VEZES: a fatura importada E o pagamento classificado como gasto.
    O mes dobra. Era o unico lado vigiado.
  * NAO CONTAR NENHUMA VEZE: o pagamento classificado como transferencia sem as
    compras importadas. O gasto do cartao desaparece e o mes parece barato - e
    e o caso dele, porque o extrato de conta corrente do Itau traz o cartao como
    uma linha so, sem detalhe.

E tem a terceira armadilha, que era silenciosa: o OFX da FATURA traz o pagamento
dela como credito. Aquele credito estava entrando como RENDA DA FAMILIA - R$
4.320 de fatura paga viravam R$ 4.320 de renda, e nao havia como consertar pela
tela, nem classificando a linha como "Pagamento de fatura".
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

MES = "2026-09-01"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def casa(client):
    from sqlalchemy import text

    from app.cli import seed_family
    from app.db.session import SessionLocal

    sufixo = uuid.uuid4().hex[:8]
    email = f"felipe.cartao.{sufixo}@exemplo.com"
    family_id = seed_family(
        name=f"Familia {sufixo}",
        titular="Felipe Ferrari",
        titular_email=email,
        titular_password="segredo-de-teste",
        conjuge="Clarissa Ferrari",
        conjuge_email=f"clarissa.cartao.{sufixo}@exemplo.com",
        conjuge_password="segredo-de-teste",
        dependentes=[],
    )
    auth = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "segredo-de-teste"}
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    corrente = client.post(
        "/api/v1/accounts", json={"name": "Itau", "type": "CONTA_CORRENTE"}, headers=headers
    ).json()
    cartao = client.post(
        "/api/v1/accounts",
        json={"name": "Itau Visa", "type": "CARTAO_CREDITO"},
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
    return {
        "headers": headers,
        "corrente": corrente["id"],
        "cartao": cartao["id"],
        "cat": cats,
    }


def lancar(client, casa, conta: str, **kw):
    corpo = {
        "account_id": conta,
        "direction": "SAIDA",
        "booked_on": "2026-09-10",
        "status": "EFETIVADA",
        **kw,
    }
    resposta = client.post("/api/v1/transactions", json=corpo, headers=casa["headers"])
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def fluxo(client, casa, mes: str = MES) -> dict:
    return client.get(
        "/api/v1/dashboard", params={"month": mes}, headers=casa["headers"]
    ).json()["cashflow"]


def cartao(client, casa) -> dict:
    return client.get(
        "/api/v1/cards/summary", params={"month": MES}, headers=casa["headers"]
    ).json()


# ---------------------------------------------------------------------------
# O credito do pagamento, dentro da fatura
# ---------------------------------------------------------------------------
def test_credito_na_conta_do_cartao_nao_e_renda(client, casa):
    """O numero que a primeira fatura importada estragava."""
    lancar(
        client, casa, casa["corrente"], direction="ENTRADA", amount="28000.00",
        description="PRO LABORE", category_id=casa["cat"]["receitas.ativa_fixa.pro_labore"],
    )
    lancar(
        client, casa, casa["cartao"], direction="ENTRADA", amount="4320.15",
        description="PAGAMENTO EFETUADO",
    )
    f = fluxo(client, casa)
    assert Decimal(f["renda"]) == Decimal("28000.00")
    assert Decimal(f["inflow"]) == Decimal("28000.00")
    # o numero nao desaparece: fica em linha propria
    assert Decimal(f["credito_no_cartao"]) == Decimal("4320.15")


def test_credito_no_cartao_nao_e_renda_nem_classificado_como_pagamento(client, casa):
    """A regra e pelo TIPO DA CONTA, nao pela categoria: classificacao erra, tipo
    de conta nao."""
    lancar(
        client, casa, casa["cartao"], direction="ENTRADA", amount="4320.15",
        description="PAGAMENTO EFETUADO",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["renda"]) == Decimal("0.00")
    assert Decimal(f["doacoes"]) == Decimal("0.00")


def test_credito_no_cartao_nasce_como_pagamento_de_fatura(client, casa):
    """Sem isto, a linha mais previsivel do extrato ficaria pedindo categoria
    todo mes, para sempre."""
    criado = lancar(
        client, casa, casa["cartao"], direction="ENTRADA", amount="4320.15",
        description="PAGAMENTO EFETUADO",
    )
    assert criado["category_id"] == casa["cat"]["transferencias.pagamento_cartao"]


def test_transferencia_que_entra_nao_e_renda(client, casa):
    lancar(
        client, casa, casa["corrente"], direction="ENTRADA", amount="5000.00",
        description="TRANSF ENTRE CONTAS",
        category_id=casa["cat"]["transferencias.entre_contas"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["renda"]) == Decimal("0.00")
    assert Decimal(f["outras_entradas"]) == Decimal("5000.00")


def test_o_que_nao_e_renda_nao_vira_doacao(client, casa):
    """O balde de doacao e o CAMINHO da categoria, nao "nao e renda". Somados,
    o Resumo diria que os sogros pagaram a fatura do cartao."""
    lancar(
        client, casa, casa["corrente"], direction="ENTRADA", amount="4320.15",
        description="DEVOLUCAO", category_id=casa["cat"]["transferencias.entre_contas"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["doacoes"]) == Decimal("0.00")
    assert Decimal(f["outras_entradas"]) == Decimal("4320.15")

    resumo = client.get(
        "/api/v1/doacoes/resumo", params={"year": 2026}, headers=casa["headers"]
    ).json()
    # e nao aparece como "doacao sem dono" na tela de doacoes
    assert Decimal(resumo["sem_doador"]) == Decimal("0.00")
    assert resumo["sem_doador_lancamentos"] == []


# ---------------------------------------------------------------------------
# A fatura paga sem as compras: o gasto que desaparecia
# ---------------------------------------------------------------------------
def test_fatura_paga_sem_compras_conhecidas_e_denunciada(client, casa):
    lancar(
        client, casa, casa["corrente"], amount="4320.15",
        description="PAGTO FATURA CARTAO 5544",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    c = cartao(client, casa)
    assert Decimal(c["bill_paid"]) == Decimal("4320.15")
    assert Decimal(c["purchases_known"]) == Decimal("0.00")
    assert Decimal(c["gap"]) == Decimal("4320.15")
    assert c["aviso_sem_detalhe"] and "não está em gasto nenhum" in c["aviso_sem_detalhe"]
    # e a tela recebe a linha para poder oferecer a saida
    assert [p["counted_as_expense"] for p in c["bill_payments"]] == [False]


def test_contar_como_gasto_fecha_o_buraco(client, casa):
    pagamento = lancar(
        client, casa, casa["corrente"], amount="4320.15",
        description="PAGTO FATURA CARTAO 5544",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    client.patch(
        f"/api/v1/transactions/{pagamento['id']}",
        json={"category_id": casa["cat"]["despesas.cartao_sem_detalhe"], "learn_rule": False},
        headers=casa["headers"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["consumo"]) == Decimal("4320.15")

    c = cartao(client, casa)
    assert Decimal(c["sem_detalhe"]) == Decimal("4320.15")
    assert Decimal(c["gap"]) == Decimal("0.00")
    assert c["aviso_sem_detalhe"] is None
    # sem compra conhecida, contar como gasto NAO e duplicata: foi o que o
    # proprio sistema sugeriu
    assert c["possible_duplicates"] == []
    assert [p["counted_as_expense"] for p in c["bill_payments"]] == [True]


def test_quando_a_fatura_chega_depois_a_duplicata_e_apontada(client, casa):
    """A mesma linha que fechava o buraco passa a ser duplicata no dia em que as
    compras entram. Sem este aviso, o mes contaria o cartao duas vezes.

    A compra e de AGOSTO porque e ela que a fatura paga em setembro cobra - e,
    com o mes do caixa, e ela que aparece como gasto de setembro. Lancar a
    compra em setembro seria montar um caso que nao acontece: a compra do dia 3
    de setembro so e cobrada na fatura seguinte.
    """
    pagamento = lancar(
        client, casa, casa["corrente"], amount="4320.15",
        description="PAGTO FATURA CARTAO 5544",
        category_id=casa["cat"]["despesas.cartao_sem_detalhe"],
    )
    assert cartao(client, casa)["possible_duplicates"] == []

    lancar(
        client, casa, casa["cartao"], amount="245.90", description="POSTO SHELL",
        booked_on="2026-08-03", category_id=casa["cat"]["despesas.transporte.gasolina"],
    )
    c = cartao(client, casa)
    assert [d["id"] for d in c["possible_duplicates"]] == [pagamento["id"]]
    assert c["aviso"] and "contando como" in c["aviso"]


def test_com_as_compras_importadas_o_pagamento_nao_conta(client, casa):
    """O caminho certo, e o que o sistema faz sozinho quando a fatura e
    importada: a compra conta, o pagamento nao.

    As compras sao de agosto: sao elas que a fatura paga em setembro cobra, e e
    por isso que pesam em setembro.
    """
    lancar(
        client, casa, casa["cartao"], amount="245.90", description="POSTO SHELL",
        booked_on="2026-08-03", category_id=casa["cat"]["despesas.transporte.gasolina"],
    )
    lancar(
        client, casa, casa["cartao"], amount="189.00", description="IFOOD",
        booked_on="2026-08-12", category_id=casa["cat"]["despesas.delivery"],
    )
    lancar(
        client, casa, casa["corrente"], amount="4320.15",
        description="PAGTO FATURA CARTAO 5544",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["consumo"]) == Decimal("434.90")
    c = cartao(client, casa)
    assert Decimal(c["total_spent"]) == Decimal("434.90")
    assert Decimal(c["gap"]) == Decimal("0.00")
    assert c["possible_duplicates"] == []


def test_a_janela_da_fatura_cobre_o_mes_anterior(client, casa):
    """A fatura paga em setembro cobra compras de agosto. Comparar so dentro do
    mes do pagamento acusaria buraco todo mes, inclusive sem buraco nenhum."""
    lancar(
        client, casa, casa["cartao"], amount="4000.00", description="COMPRAS DE AGOSTO",
        booked_on="2026-08-20", category_id=casa["cat"]["despesas.mercado"],
    )
    lancar(
        client, casa, casa["corrente"], amount="4320.15",
        description="PAGTO FATURA CARTAO 5544",
        category_id=casa["cat"]["transferencias.pagamento_cartao"],
    )
    c = cartao(client, casa)
    assert Decimal(c["purchases_known"]) == Decimal("4000.00")
    assert Decimal(c["gap"]) == Decimal("0.00")
    assert c["aviso_sem_detalhe"] is None


# ---------------------------------------------------------------------------
# As categorias de entrada que ele pediu
# ---------------------------------------------------------------------------
def test_as_categorias_de_entrada_que_ele_pediu(casa):
    assert casa["cat"]["receitas.ativa_fixa.salario.felipe"]
    assert casa["cat"]["receitas.ativa_fixa.salario.clarissa"]
    assert casa["cat"]["receitas.passiva.dividendos.check"]
    assert casa["cat"]["receitas.passiva.dividendos.ldm"]


def test_salario_e_tributavel_e_dividendo_e_isento(client, casa):
    """O que faz a diferenca no IR, e o motivo de elas nascerem debaixo das maes
    que o motor ja entende em vez de numa arvore nova."""
    arvore = client.get("/api/v1/categories", headers=casa["headers"]).json()
    achatada: dict[str, dict] = {}

    def andar(nos: list[dict]) -> None:
        for no in nos:
            achatada[no["path"]] = no
            andar(no["children"])

    andar(arvore)
    assert achatada["receitas.ativa_fixa.salario.felipe"]["ir_treatment"] == "TRIBUTAVEL_TABELA"
    assert achatada["receitas.ativa_fixa.salario.clarissa"]["ir_treatment"] == "TRIBUTAVEL_TABELA"
    assert (
        achatada["receitas.passiva.dividendos.check"]["ir_treatment"]
        == "ISENTO_NAO_TRIBUTAVEL"
    )
    assert achatada["receitas.passiva.dividendos.ldm"]["ir_treatment"] == "ISENTO_NAO_TRIBUTAVEL"
    # e as duas sao renda da familia, ao contrario de doacao e transferencia
    assert achatada["receitas.ativa_fixa.salario.felipe"]["counts_as_income"] is True
    assert achatada["receitas.passiva.dividendos.ldm"]["counts_as_income"] is True


def test_salario_e_dividendo_entram_na_renda_e_no_ir_certo(client, casa):
    lancar(
        client, casa, casa["corrente"], direction="ENTRADA", amount="12000.00",
        description="SALARIO CLARISSA",
        category_id=casa["cat"]["receitas.ativa_fixa.salario.clarissa"],
    )
    lancar(
        client, casa, casa["corrente"], direction="ENTRADA", amount="9000.00",
        description="DIVIDENDOS LDM",
        category_id=casa["cat"]["receitas.passiva.dividendos.ldm"],
    )
    f = fluxo(client, casa)
    assert Decimal(f["renda"]) == Decimal("21000.00")

    ir = client.get("/api/v1/tax/2026", headers=casa["headers"]).json()
    assert Decimal(ir["taxable_income"]) == Decimal("12000.00")
    assert Decimal(ir["exempt_income"]) == Decimal("9000.00")


# ---------------------------------------------------------------------------
# A fatura que vem com o sinal da divida
# ---------------------------------------------------------------------------
# "No inicio ele poe o valor total como negativo e todo o resto sai discriminado
# como positivo. (...) alem de aparecer como saldo no sistema, as categorias saem
# invertidas."
#
# Lida com a regra do extrato de CONTA (positivo = entrou), a fatura inteira vira
# ao contrario: as compras entram como renda e o total da fatura vira o unico
# gasto do mes. Ver app/services/importers/fatura.py.
FATURA_COM_SINAL_DA_DIVIDA = (
    "Data;Lancamento;Valor\n"
    "01/09/2026;TOTAL DA FATURA;-1035,80\n"
    "03/09/2026;POSTO SHELL AV BRASIL;245,90\n"
    "12/09/2026;IFOOD CLUB;189,00\n"
    "15/09/2026;SUPERMERCADO PAO DE ACUCAR;600,90\n"
)


def enviar(client, casa, conta: str, texto: str, nome: str = "fatura.csv") -> dict:
    resposta = client.post(
        "/api/v1/imports",
        data={"account_id": conta},
        files={"file": (nome, texto.encode("utf-8"), "text/csv")},
        headers=casa["headers"],
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_a_fatura_com_compra_positiva_entra_como_gasto(client, casa):
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA)
    linhas = lote["preview"]

    assert [linha["direction"] for linha in linhas] == ["SAIDA"] * 3
    assert sum(Decimal(linha["amount"]) for linha in linhas) == Decimal("1035.80")
    # e nenhuma linha sugere categoria de receita
    assert all(linha["suggested_category_name"] != "Salário" for linha in linhas)


def test_o_total_da_fatura_nao_entra_na_conferencia(client, casa):
    """Importado junto, ele cobra o mes duas vezes - a conta em dobro que ele
    tinha levantado."""
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA)
    assert lote["rows_detected"] == 3
    assert all("TOTAL" not in linha["description"] for linha in lote["preview"])
    assert any("resumo" in aviso.lower() for aviso in lote["warnings"])


def test_a_inversao_e_dita_na_tela(client, casa):
    """Correcao silenciosa em dinheiro e a que ninguem confere."""
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA)
    assert any("cartao" in aviso.lower() for aviso in lote["warnings"])


def test_a_fatura_importada_vira_gasto_no_mes_em_que_ela_e_paga(client, casa):
    """Do arquivo ate o Resumo, sem ninguem corrigir nada na mao.

    As compras sao de setembro e pesam em OUTUBRO: sem dia de fechamento
    cadastrado, a fatura que as cobra vence em 10 de outubro, e e nesse dia que
    o dinheiro sai da conta. Em setembro o Resumo nao mostra nada - naquele mes
    nao saiu nada da conta por causa dessas compras.
    """
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA)
    confirmado = client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=casa["headers"]
    )
    assert confirmado.status_code == 200, confirmado.text

    setembro = fluxo(client, casa)
    assert Decimal(setembro["consumo"]) == Decimal("0.00")

    outubro = fluxo(client, casa, mes="2026-10-01")
    assert Decimal(outubro["consumo"]) == Decimal("1035.80")
    # e nada disso virou renda
    assert Decimal(outubro["renda"]) == Decimal("0.00")
    assert Decimal(outubro["inflow"]) == Decimal("0.00")


def test_o_extrato_da_conta_corrente_nao_e_invertido(client, casa):
    """So a fatura fala pelo lado da divida.

    Em conta corrente o deposito positivo E entrada. Inverter ali transformaria
    a renda do mes em gasto - erro maior do que o que esta sendo corrigido.
    """
    extrato = (
        "Data;Historico;Valor\n"
        "05/09/2026;PRO LABORE;28000,00\n"
        "06/09/2026;SUPERMERCADO;-600,90\n"
        "07/09/2026;POSTO SHELL;-245,90\n"
    )
    lote = enviar(client, casa, casa["corrente"], extrato, nome="extrato.csv")
    por_descricao = {linha["description"]: linha["direction"] for linha in lote["preview"]}
    assert por_descricao["PRO LABORE"] == "ENTRADA"
    assert por_descricao["SUPERMERCADO"] == "SAIDA"
    assert not any("cartao" in aviso.lower() for aviso in lote["warnings"])


def test_fatura_que_ja_vem_certa_continua_certa(client, casa):
    """Metade dos bancos exporta a fatura com a compra negativa."""
    texto = (
        "Data;Lancamento;Valor\n"
        "03/09/2026;POSTO SHELL;-245,90\n"
        "12/09/2026;IFOOD CLUB;-189,00\n"
        "15/09/2026;SUPERMERCADO;-600,90\n"
        "10/09/2026;PAGAMENTO EFETUADO;4320,15\n"
    )
    lote = enviar(client, casa, casa["cartao"], texto, nome="fatura2.csv")
    por_descricao = {linha["description"]: linha["direction"] for linha in lote["preview"]}
    assert por_descricao["POSTO SHELL"] == "SAIDA"
    assert por_descricao["PAGAMENTO EFETUADO"] == "ENTRADA"


# ---------------------------------------------------------------------------
# A saida de emergencia: virar a linha na conferencia
# ---------------------------------------------------------------------------
# A correcao automatica cobre o que se sabe hoje. Leiaute de banco nao acaba, e a
# ultima vez que uma linha entrou do lado errado nao havia conserto pela tela -
# so no banco de dados. Agora vira na conferencia, antes de gravar.
def test_virar_a_linha_na_conferencia(client, casa):
    extrato = (
        "Data;Historico;Valor\n"
        "05/09/2026;DEPOSITO ESTRANHO;1500,00\n"
        "06/09/2026;SUPERMERCADO;-600,90\n"
    )
    lote = enviar(client, casa, casa["corrente"], extrato, nome="estranho.csv")
    linha = next(
        linha for linha in lote["preview"] if linha["description"] == "DEPOSITO ESTRANHO"
    )
    assert linha["direction"] == "ENTRADA"

    resposta = client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={"direction_overrides": {str(linha["index"]): "SAIDA"}},
        headers=casa["headers"],
    )
    assert resposta.status_code == 200, resposta.text

    lancamentos = client.get(
        "/api/v1/transactions",
        params={"start": "2026-09-01", "end": "2026-09-30"},
        headers=casa["headers"],
    ).json()
    virado = next(t for t in lancamentos if t["description"] == "DEPOSITO ESTRANHO")
    assert virado["direction"] == "SAIDA"
    # a sugestao era do outro lado: "Salario" num gasto nao quer dizer nada
    categorias = client.get("/api/v1/categories", headers=casa["headers"]).json()

    achatada: dict[str, str] = {}

    def andar(nos):
        for no in nos:
            achatada[str(no["id"])] = no["path"]
            andar(no["children"])

    andar(categorias)
    assert achatada[virado["category_id"]].startswith("despesas")


def test_virar_a_linha_nao_cria_lancamento_repetido_depois(client, casa):
    """A impressao digital tem a direcao dentro dela.

    Guardada a antiga, a mesma linha reimportada no mes seguinte pareceria linha
    nova - e o gasto entraria duas vezes, que e o erro que a importacao existe
    para evitar.
    """
    extrato = "Data;Historico;Valor\n05/09/2026;PIX RECEBIDO;1500,00\n"
    primeiro = enviar(client, casa, casa["corrente"], extrato, nome="pix1.csv")
    linha = primeiro["preview"][0]
    client.post(
        f"/api/v1/imports/{primeiro['id']}/confirm",
        json={"direction_overrides": {str(linha["index"]): "SAIDA"}},
        headers=casa["headers"],
    ).raise_for_status()

    # o mesmo arquivo de novo: a linha ja gravada tem de ser reconhecida
    segundo = enviar(client, casa, casa["corrente"], extrato, nome="pix2.csv")
    repetida = segundo["preview"][0]
    client.post(
        f"/api/v1/imports/{segundo['id']}/confirm",
        json={"direction_overrides": {str(repetida["index"]): "SAIDA"}},
        headers=casa["headers"],
    ).raise_for_status()

    lancamentos = client.get(
        "/api/v1/transactions",
        params={"start": "2026-09-01", "end": "2026-09-30"},
        headers=casa["headers"],
    ).json()
    assert len([t for t in lancamentos if t["description"] == "PIX RECEBIDO"]) == 1


def test_lado_invalido_e_recusado_com_frase(client, casa):
    extrato = "Data;Historico;Valor\n05/09/2026;PIX;1500,00\n"
    lote = enviar(client, casa, casa["corrente"], extrato, nome="pix3.csv")
    resposta = client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={"direction_overrides": {"0": "TRANSFERENCIA"}},
        headers=casa["headers"],
    )
    assert resposta.status_code == 422
    assert "ENTRADA" in resposta.json()["detail"]


# ---------------------------------------------------------------------------
# Desfazer uma importacao
# ---------------------------------------------------------------------------
# A fatura invertida que ele importou antes da correcao precisa SAIR antes de o
# arquivo certo entrar. E reimportar nao resolveria sozinho: a direcao entra na
# impressao digital, entao as linhas corrigidas nao sao reconhecidas como
# repetidas - a familia terminaria com as duas versoes somadas.
def test_desfazer_apaga_os_lancamentos_daquele_arquivo(client, casa):
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA, nome="f1.csv")
    client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=casa["headers"]
    ).raise_for_status()
    # outubro: as compras de setembro sao cobradas na fatura que vence la
    assert Decimal(fluxo(client, casa, mes="2026-10-01")["consumo"]) == Decimal("1035.80")

    resposta = client.post(
        f"/api/v1/imports/{lote['id']}/desfazer", headers=casa["headers"]
    )
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["lancamentos_apagados"] == 3
    assert Decimal(fluxo(client, casa, mes="2026-10-01")["consumo"]) == Decimal("0.00")


def test_desfazer_nao_toca_no_que_foi_lancado_a_mao(client, casa):
    """Apaga o que veio do arquivo, e so isso."""
    lancar(
        client, casa, casa["corrente"], amount="80.00", description="PADARIA EM DINHEIRO",
        category_id=casa["cat"]["despesas.restaurantes"],
    )
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA, nome="f2.csv")
    client.post(
        f"/api/v1/imports/{lote['id']}/confirm", json={}, headers=casa["headers"]
    ).raise_for_status()

    client.post(
        f"/api/v1/imports/{lote['id']}/desfazer", headers=casa["headers"]
    ).raise_for_status()

    # o lancamento a mao foi na conta corrente, entao continua em setembro
    assert Decimal(fluxo(client, casa)["consumo"]) == Decimal("80.00")
    assert Decimal(fluxo(client, casa, mes="2026-10-01")["consumo"]) == Decimal("0.00")


def test_depois_de_desfazer_o_mesmo_arquivo_entra_de_novo(client, casa):
    """E o caminho que ele vai percorrer: desfazer o errado, importar o certo."""
    primeiro = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA, nome="f3.csv")
    client.post(
        f"/api/v1/imports/{primeiro['id']}/confirm", json={}, headers=casa["headers"]
    ).raise_for_status()
    client.post(
        f"/api/v1/imports/{primeiro['id']}/desfazer", headers=casa["headers"]
    ).raise_for_status()

    segundo = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA, nome="f4.csv")
    # nenhuma linha pode vir marcada como repetida: as antigas sumiram
    assert all(not linha["duplicate"] for linha in segundo["preview"])
    client.post(
        f"/api/v1/imports/{segundo['id']}/confirm", json={}, headers=casa["headers"]
    ).raise_for_status()
    assert Decimal(fluxo(client, casa, mes="2026-10-01")["consumo"]) == Decimal("1035.80")


def test_desfazer_importacao_de_outra_familia_nao_existe(client, casa):
    lote = enviar(client, casa, casa["cartao"], FATURA_COM_SINAL_DA_DIVIDA, nome="f5.csv")
    outra = client.post(
        "/api/v1/auth/login",
        json={"email": "ninguem@exemplo.com", "password": "errado"},
    )
    assert outra.status_code in (401, 422)
    # sem token, nem chega no recurso
    assert client.post(f"/api/v1/imports/{lote['id']}/desfazer").status_code == 401


def test_virar_o_extrato_inteiro_de_uma_vez(client, casa):
    """O botao "inverter o extrato inteiro": um toque em vez de trinta.

    O caminho que a tela usa e este - uma troca por linha, todas de uma vez -,
    porque assim o servidor nao precisa saber se a inversao veio de um toque ou
    de trinta, e a volta atras e so mandar menos linhas.
    """
    extrato = (
        "Data;Lancamento;Valor\n"
        "03/09/2026;POSTO SHELL;-245,90\n"
        "12/09/2026;IFOOD CLUB;-189,00\n"
        "15/09/2026;SUPERMERCADO;-600,90\n"
    )
    # conta corrente: aqui o sistema NAO inverte sozinho, e o botao e a saida
    lote = enviar(client, casa, casa["corrente"], extrato, nome="virado.csv")
    assert [linha["direction"] for linha in lote["preview"]] == ["SAIDA"] * 3

    resposta = client.post(
        f"/api/v1/imports/{lote['id']}/confirm",
        json={
            "direction_overrides": {
                str(linha["index"]): "ENTRADA" for linha in lote["preview"]
            }
        },
        headers=casa["headers"],
    )
    assert resposta.status_code == 200, resposta.text

    lancamentos = client.get(
        "/api/v1/transactions",
        params={"start": "2026-09-01", "end": "2026-09-30"},
        headers=casa["headers"],
    ).json()
    viradas = [t for t in lancamentos if t["description"] in
               ("POSTO SHELL", "IFOOD CLUB", "SUPERMERCADO")]
    assert len(viradas) == 3
    assert {t["direction"] for t in viradas} == {"ENTRADA"}
    # e nenhuma delas conta como gasto do mes
    assert Decimal(fluxo(client, casa)["consumo"]) == Decimal("0.00")
