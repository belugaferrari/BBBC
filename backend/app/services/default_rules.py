"""Regras de fornecedor que ja nascem com a familia.

Sao um ponto de partida, nao verdade absoluta: a primeira vez que voce corrigir
uma delas, a correcao vira uma regra aprendida com prioridade melhor e passa a
mandar. O objetivo aqui e que o primeiro extrato importado chegue com a maior
parte ja preenchida, esperando um "ok", em vez de 200 linhas em branco.

Os padroes sao casados contra a descricao normalizada (minuscula, sem acento,
sem o ruido de extrato), entao 'pao de acucar' pega 'PAO DE ACUCAR 1234'.

Entre duas regras que casam, ganha a de PADRAO MAIS LONGO - quem decide isso e o
`categorize`, nao a ordem desta lista. E o que faz 'uber eats' vencer 'uber' e
'pagamento de fatura' vencer 'fatura cartao'. A lista esta agrupada por assunto
para ser lida, e nao para ser avaliada nesta ordem; mesmo assim o especifico vem
escrito antes do geral, porque quem for mexer aqui vai ler de cima para baixo.
"""

from __future__ import annotations

# (padrao, caminho da categoria)
DEFAULT_MERCHANT_RULES: list[tuple[str, str]] = [
    # --- pagamento de fatura: PRIMEIRO de todos --------------------------------
    # A compra no cartao ja foi lancada no dia dela. Quando a fatura e paga, o
    # dinheiro sai da conta corrente - e se isso entrasse como gasto, cada compra
    # seria contada duas vezes. A categoria de transferencia nao conta como
    # consumo, e e ela que impede a duplicata.
    ("pagamento de fatura", "transferencias.pagamento_cartao"),
    ("pagamento fatura", "transferencias.pagamento_cartao"),
    ("pag fatura", "transferencias.pagamento_cartao"),
    ("pagto fatura", "transferencias.pagamento_cartao"),
    ("pagamento cartao", "transferencias.pagamento_cartao"),
    ("fatura cartao", "transferencias.pagamento_cartao"),
    ("saldo fatura anterior", "transferencias.pagamento_cartao"),
    ("transferencia entre contas", "transferencias.entre_contas"),
    ("aplicacao automatica", "transferencias.entre_contas"),
    ("resgate automatico", "transferencias.entre_contas"),

    # --- delivery de comida (antes de 'uber', de proposito) -------------------
    ("ifood", "despesas.delivery"),
    # como a fatura do Itau escreve o iFood; o casamento certo e por prefixo
    # (DEFAULT_PREFIX_RULES), e este aqui pega a forma escrita por extenso
    ("ifd", "despesas.delivery"),
    ("rappi", "despesas.delivery"),
    ("uber eats", "despesas.delivery"),
    ("99food", "despesas.delivery"),
    ("99 food", "despesas.delivery"),
    ("cheeta", "despesas.delivery"),
    ("aiqfome", "despesas.delivery"),
    ("zedelivery", "despesas.delivery"),
    ("ze delivery", "despesas.delivery"),
    ("daki", "despesas.delivery"),

    # --- restaurantes que so se reconhecem pelo nome da empresa ---------------
    # Razao social no lugar do nome fantasia e o normal na fatura de cartao.
    ("casottisouzaltda", "despesas.restaurantes.restaurante"),

    # --- transporte por aplicativo --------------------------------------------
    ("uber", "despesas.transporte.aplicativo"),
    ("99app", "despesas.transporte.aplicativo"),
    ("99 tecnologia", "despesas.transporte.aplicativo"),
    ("99pop", "despesas.transporte.aplicativo"),
    ("cabify", "despesas.transporte.aplicativo"),
    ("indriver", "despesas.transporte.aplicativo"),
    ("taxi", "despesas.transporte.aplicativo"),

    # --- gasolina -------------------------------------------------------------
    ("posto", "despesas.transporte.gasolina"),
    ("ipiranga", "despesas.transporte.gasolina"),
    ("shell", "despesas.transporte.gasolina"),
    ("petrobras", "despesas.transporte.gasolina"),
    ("br mania", "despesas.transporte.gasolina"),
    ("ale combust", "despesas.transporte.gasolina"),
    ("combustivel", "despesas.transporte.gasolina"),
    ("auto posto", "despesas.transporte.gasolina"),

    # --- estacionamento -------------------------------------------------------
    ("estacionamento", "despesas.transporte.estacionamento"),
    ("estapar", "despesas.transporte.estacionamento"),
    ("multipark", "despesas.transporte.estacionamento"),
    ("zona azul", "despesas.transporte.estacionamento"),
    ("parking", "despesas.transporte.estacionamento"),

    # --- pedagio e tag --------------------------------------------------------
    ("sem parar", "despesas.transporte.pedagio_tag"),
    ("semparar", "despesas.transporte.pedagio_tag"),
    ("conectcar", "despesas.transporte.pedagio_tag"),
    ("veloe", "despesas.transporte.pedagio_tag"),
    ("taggy", "despesas.transporte.pedagio_tag"),
    ("move mais", "despesas.transporte.pedagio_tag"),
    ("pedagio", "despesas.transporte.pedagio_tag"),
    ("autoban", "despesas.transporte.pedagio_tag"),
    ("ecovias", "despesas.transporte.pedagio_tag"),
    ("ccr ", "despesas.transporte.pedagio_tag"),

    # --- manutencao do carro --------------------------------------------------
    ("oficina", "despesas.transporte.manutencao"),
    ("autocenter", "despesas.transporte.manutencao"),
    ("auto center", "despesas.transporte.manutencao"),
    ("pneus", "despesas.transporte.manutencao"),
    ("lava rapido", "despesas.transporte.manutencao"),
    ("funilaria", "despesas.transporte.manutencao"),

    # --- mercado --------------------------------------------------------------
    ("supermercado", "despesas.mercado"),
    ("mercado", "despesas.mercado"),
    ("assai", "despesas.mercado"),
    ("atacadao", "despesas.mercado"),
    ("carrefour", "despesas.mercado"),
    ("pao de acucar", "despesas.mercado"),
    ("angeloni", "despesas.mercado"),
    ("zaffari", "despesas.mercado"),
    ("hortifruti", "despesas.mercado"),
    ("sam s club", "despesas.mercado"),
    ("tenda atacado", "despesas.mercado"),

    # --- restaurantes ---------------------------------------------------------
    ("padaria", "despesas.restaurantes.padaria"),
    ("panificadora", "despesas.restaurantes.padaria"),
    ("lanchonete", "despesas.restaurantes.padaria"),
    ("starbucks", "despesas.restaurantes.cafe"),
    ("cafeteria", "despesas.restaurantes.cafe"),
    ("restaurante", "despesas.restaurantes.restaurante"),
    ("churrascaria", "despesas.restaurantes.restaurante"),
    ("pizzaria", "despesas.restaurantes.restaurante"),
    ("outback", "despesas.restaurantes.restaurante"),
    ("mcdonald", "despesas.restaurantes.restaurante"),
    ("burger king", "despesas.restaurantes.restaurante"),
    ("madero", "despesas.restaurantes.restaurante"),
    ("subway", "despesas.restaurantes.restaurante"),
    ("habib", "despesas.restaurantes.restaurante"),

    # --- market places --------------------------------------------------------
    ("mercadolivre", "despesas.market_places"),
    ("mercado livre", "despesas.market_places"),
    ("mercadopago", "despesas.market_places"),
    ("amazon", "despesas.market_places"),
    ("shopee", "despesas.market_places"),
    ("aliexpress", "despesas.market_places"),
    ("shein", "despesas.market_places"),
    ("magazine luiza", "despesas.market_places"),
    ("magalu", "despesas.market_places"),
    ("americanas", "despesas.market_places"),
    ("casas bahia", "despesas.market_places"),

    # --- assinaturas (dentro de gastos mensais) -------------------------------
    ("netflix", "despesas.gastos_mensais.assinaturas.streaming"),
    ("spotify", "despesas.gastos_mensais.assinaturas.streaming"),
    ("disney", "despesas.gastos_mensais.assinaturas.streaming"),
    ("hbo", "despesas.gastos_mensais.assinaturas.streaming"),
    ("max.com", "despesas.gastos_mensais.assinaturas.streaming"),
    ("globoplay", "despesas.gastos_mensais.assinaturas.streaming"),
    ("youtube premium", "despesas.gastos_mensais.assinaturas.streaming"),
    ("prime video", "despesas.gastos_mensais.assinaturas.streaming"),
    ("deezer", "despesas.gastos_mensais.assinaturas.streaming"),
    ("openai", "despesas.gastos_mensais.assinaturas.softwares"),
    ("chatgpt", "despesas.gastos_mensais.assinaturas.softwares"),
    ("anthropic", "despesas.gastos_mensais.assinaturas.softwares"),
    ("claude", "despesas.gastos_mensais.assinaturas.softwares"),
    ("github", "despesas.gastos_mensais.assinaturas.softwares"),
    ("adobe", "despesas.gastos_mensais.assinaturas.softwares"),
    ("microsoft", "despesas.gastos_mensais.assinaturas.softwares"),
    ("google one", "despesas.gastos_mensais.assinaturas.softwares"),
    ("icloud", "despesas.gastos_mensais.assinaturas.softwares"),
    ("apple.com", "despesas.gastos_mensais.assinaturas.softwares"),
    ("kindle", "despesas.gastos_mensais.assinaturas.livros"),
    ("livraria", "despesas.gastos_mensais.assinaturas.livros"),

    # --- gastos mensais: as contas da casa ------------------------------------
    ("sabesp", "despesas.gastos_mensais.agua"),
    ("copasa", "despesas.gastos_mensais.agua"),
    ("casan", "despesas.gastos_mensais.agua"),
    ("saneamento", "despesas.gastos_mensais.agua"),
    ("enel", "despesas.gastos_mensais.luz"),
    ("cemig", "despesas.gastos_mensais.luz"),
    ("cpfl", "despesas.gastos_mensais.luz"),
    ("celesc", "despesas.gastos_mensais.luz"),
    ("coelba", "despesas.gastos_mensais.luz"),
    ("light servicos", "despesas.gastos_mensais.luz"),
    ("energia eletrica", "despesas.gastos_mensais.luz"),
    ("comgas", "despesas.gastos_mensais.gas"),
    ("ultragaz", "despesas.gastos_mensais.gas"),
    ("liquigas", "despesas.gastos_mensais.gas"),
    ("vivo", "despesas.gastos_mensais.telefone"),
    ("claro", "despesas.gastos_mensais.telefone"),
    ("tim ", "despesas.gastos_mensais.telefone"),
    ("oi movel", "despesas.gastos_mensais.telefone"),
    ("net servicos", "despesas.gastos_mensais.internet"),
    ("internet", "despesas.gastos_mensais.internet"),
    ("fibra", "despesas.gastos_mensais.internet"),

    # --- condominio -----------------------------------------------------------
    ("condominio", "despesas.condominio"),

    # --- saude (farmacia separada: remedio nao e dedutivel) -------------------
    ("drogaria", "despesas.saude.farmacia"),
    ("drogasil", "despesas.saude.farmacia"),
    ("droga raia", "despesas.saude.farmacia"),
    ("raia", "despesas.saude.farmacia"),
    ("pacheco", "despesas.saude.farmacia"),
    ("farmacia", "despesas.saude.farmacia"),
    ("panvel", "despesas.saude.farmacia"),
    ("pague menos", "despesas.saude.farmacia"),
    ("unimed", "despesas.saude.plano_de_saude"),
    ("amil", "despesas.saude.plano_de_saude"),
    ("sulamerica", "despesas.saude.plano_de_saude"),
    ("hapvida", "despesas.saude.plano_de_saude"),
    ("bradesco saude", "despesas.saude.plano_de_saude"),
    ("plano de saude", "despesas.saude.plano_de_saude"),
    ("laboratorio", "despesas.saude.consultas_exames"),
    ("clinica", "despesas.saude.consultas_exames"),
    ("hospital", "despesas.saude.consultas_exames"),
    ("odonto", "despesas.saude.odontologia"),
    ("psicolog", "despesas.saude.terapias"),
    ("fisioterap", "despesas.saude.terapias"),

    # --- educacao -------------------------------------------------------------
    ("colegio", "despesas.educacao.escola"),
    ("escola", "despesas.educacao.escola"),
    ("mensalidade escolar", "despesas.educacao.escola"),
    ("faculdade", "despesas.educacao.faculdade"),
    ("universidade", "despesas.educacao.faculdade"),
    ("material escolar", "despesas.educacao.materiais"),
    ("papelaria", "despesas.educacao.materiais"),

    # --- limpeza --------------------------------------------------------------
    ("faxina", "despesas.limpeza.diarista"),
    ("diarista", "despesas.limpeza.diarista"),

    # --- criacao --------------------------------------------------------------
    ("ri happy", "despesas.criacao.brinquedos"),
    ("pbkids", "despesas.criacao.brinquedos"),
    ("brinquedo", "despesas.criacao.brinquedos"),

    # --- gastos anuais --------------------------------------------------------
    ("ipva", "despesas.gastos_anuais.ipva"),
    ("iptu", "despesas.gastos_anuais.iptu"),
    ("licenciamento", "despesas.gastos_anuais.licenciamento"),
    ("seguro auto", "despesas.gastos_anuais.seguro_carro"),
    ("seguro", "despesas.gastos_anuais.seguro_carro"),
    ("anuidade", "despesas.gastos_anuais.anuidades"),

    # --- financiamentos -------------------------------------------------------
    ("juros financiamento", "despesas.financiamentos.juros"),
    ("amortizacao", "despesas.financiamentos.amortizacao"),
    ("prestacao financiamento", "despesas.financiamentos.juros"),

    # --- Cla PJ ---------------------------------------------------------------
    # Custo de manter a empresa da Clarissa de pe.
    ("darf", "despesas.cla_pj.darf"),
    ("das simples", "despesas.cla_pj.darf"),
    ("contabilidade", "despesas.cla_pj.contabilidade"),
    ("contador", "despesas.cla_pj.contabilidade"),
    ("nota fiscal", "despesas.cla_pj.nota_fiscal"),

    # --- gastos unicos --------------------------------------------------------
    ("multa", "despesas.gastos_unicos.multas"),

    # --- siglas de extrato de conta corrente ----------------------------------
    # Fatura de cartao traz nome de loja; extrato de conta corrente traz sigla de
    # banco. Sao mundos diferentes, e o catalogo so conhecia o primeiro - o
    # primeiro extrato de conta corrente dele chegou com 1 linha de 14 sugerida.
    ("financ imobiliario", "despesas.financiamentos"),
    ("financiamento imobiliario", "despesas.financiamentos"),
    ("credito imobiliario", "despesas.financiamentos"),
    # A aplicacao automatica do banco move dinheiro todo dia entre a conta e o
    # fundo. Nao e gasto nem receita: e o mesmo dinheiro mudando de lugar, e
    # contado como saida encheria o mes de despesa que nunca existiu.
    ("aplic aut", "transferencias.entre_contas"),
    ("aplicacao aut", "transferencias.entre_contas"),
    ("resgate aut", "transferencias.entre_contas"),
    ("tarifa", "despesas.gastos_anuais.anuidades"),
    ("cesta de servicos", "despesas.gastos_anuais.anuidades"),
    ("pacote de servicos", "despesas.gastos_anuais.anuidades"),
    ("iof", "despesas.gastos_anuais.anuidades"),

    # --- receitas -------------------------------------------------------------
    # O rendimento da aplicacao automatica. Precisa de prioridade porque a
    # descricao inteira - "REND PAGO APLIC AUT MAIS" - casa tambem com a regra da
    # aplicacao acima, e as duas tem o mesmo tamanho: sem desempate, qual das
    # duas ganha seria sorte.
    ("rend pago", "receitas.passiva.renda_fixa"),
    ("pro labore", "receitas.ativa_fixa.pro_labore"),
    ("pro-labore", "receitas.ativa_fixa.pro_labore"),
    ("distribuicao de lucros", "receitas.ativa_variavel.lucros"),
    ("distribuicao lucros", "receitas.ativa_variavel.lucros"),
    ("dividendos", "receitas.passiva.dividendos"),
    ("rendimento", "receitas.passiva.renda_fixa"),
]

# Prioridade das regras de catalogo. Fica acima de 100 (o padrao) para que
# qualquer regra aprendida com a correcao do usuario (prioridade 50) vença.
CATALOG_RULE_PRIORITY = 90
CATALOG_RULE_CONFIDENCE = "0.600"

# ---------------------------------------------------------------------------
# Padroes que precisam vencer o desempate por tamanho
# ---------------------------------------------------------------------------
# O desempate normal e por tamanho do padrao, e isso erra num caso concreto:
# "IFOOD *RESTAURANTE SAO JOSE" casa com 'ifood' (5 letras) e com 'restaurante'
# (11), e o mais longo ganha - o jantar entregue em casa entrava como refeicao
# fora. O nome do estabelecimento vem de brinde na descricao; quem paga a conta
# e o aplicativo, e e ele que define a natureza do gasto. Uma padaria pedida pelo
# iFood continua sendo delivery.
#
# Estes padroes recebem prioridade melhor que o resto do catalogo, e continuam
# atras de qualquer regra aprendida com uma correcao do usuario (prioridade 50) -
# se ele discordar uma vez, a correcao dele e que passa a valer.
PRIORIDADE_PLATAFORMA = 80

# ---------------------------------------------------------------------------
# Regras que casam pelo COMECO da descricao
# ---------------------------------------------------------------------------
# Algumas marcas se reconhecem pelas primeiras letras e por mais nada. O cartao
# escreve "Acm Alphaville Barueri Bra" para a academia dele - e "Alphaville Sao
# Paulo Bra", sem o Acm, e outra coisa inteiramente. Procurar "acm" no meio do
# texto encontraria as duas, e qualquer outra palavra que tenha essas tres
# letras; casar pelo comeco encontra so a primeira.
#
# Sao poucos de proposito. Prefixo e mais arriscado que palavra inteira: o
# banco muda o leiaute, a descricao ganha um prefixo novo na frente, e a regra
# para de casar em silencio. Entao so entra aqui o que NAO da para reconhecer
# de outro jeito.
DEFAULT_PREFIX_RULES: list[tuple[str, str]] = [
    # "ACM Alphaville" - a academia dele. Sem o prefixo, "acm" pegaria texto no
    # meio de outras palavras.
    ("acm", "despesas.gastos_mensais.academia"),
    # "Ifd*camarada", "Ifd*organizacao": e como a fatura do Itau escreve o
    # iFood. O nome do restaurante vem depois, e e o aplicativo que define a
    # natureza do gasto - uma padaria pedida pelo iFood continua sendo delivery.
    ("ifd", "despesas.delivery"),
    # "Sam S Tambore" - o Sam's Club. O apostrofo some na normalizacao.
    ("sam s", "despesas.mercado"),
    # "Beep Saude" - atendimento e exames em casa.
    ("beep", "despesas.saude.consultas_exames"),
]

# "REND PAGO APLIC AUT MAIS" e o terceiro caso, e nao e sobre plataforma: a
# descricao casa com 'rend pago' (a receita) e com 'aplic aut' (a transferencia),
# e as duas tem nove letras. Empate exato e pior que erro: a resposta passa a
# depender de qual regra o banco devolveu primeiro.
PADROES_DE_PLATAFORMA = frozenset({
    "rend pago",
    # aplicativos de entrega: o nome do restaurante vem na descricao
    "ifood", "ifd", "rappi", "uber eats", "99food", "99 food", "cheeta", "aiqfome",
    "zedelivery", "ze delivery", "daki",
    # pagamento de fatura: "PAGAMENTO FATURA CARTAO MERCADO PAGO" nao e compra
    # em market place, e contar a fatura como gasto dobraria o mes
    "pagamento de fatura", "pagamento fatura", "pag fatura", "pagto fatura",
    "pagamento cartao", "fatura cartao", "saldo fatura anterior",
})


def prioridade_de(padrao: str) -> int:
    """Prioridade da regra de catalogo para este padrao."""
    return PRIORIDADE_PLATAFORMA if padrao in PADROES_DE_PLATAFORMA else CATALOG_RULE_PRIORITY
