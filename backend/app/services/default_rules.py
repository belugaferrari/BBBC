"""Regras de fornecedor que ja nascem com a familia.

Sao um ponto de partida, nao verdade absoluta: a primeira vez que voce corrigir
uma delas, a correcao vira uma regra aprendida com prioridade melhor e passa a
mandar. O objetivo aqui e que o primeiro extrato importado ja chegue com a
maior parte classificada, em vez de 200 linhas em branco.

Os padroes sao casados contra a descricao normalizada (minuscula, sem acento,
sem o ruido de extrato), entao 'pao de acucar' pega 'PAO DE ACUCAR 1234'.
"""

from __future__ import annotations

# (padrao, caminho da categoria). Padroes mais especificos vem antes:
# 'uber eats' precisa ser avaliado antes de 'uber'.
DEFAULT_MERCHANT_RULES: list[tuple[str, str]] = [
    # --- aplicativo de comida (antes de 'uber', de proposito) --------------
    ("ifood", "despesas.aplicativo_comida"),
    ("rappi", "despesas.aplicativo_comida"),
    ("uber eats", "despesas.aplicativo_comida"),
    ("aiqfome", "despesas.aplicativo_comida"),
    ("zedelivery", "despesas.aplicativo_comida"),

    # --- transportes -------------------------------------------------------
    ("uber", "despesas.transportes"),
    ("99app", "despesas.transportes"),
    ("99 tecnologia", "despesas.transportes"),
    ("cabify", "despesas.transportes"),
    ("taxi", "despesas.transportes"),

    # --- combustivel -------------------------------------------------------
    ("posto", "despesas.combustivel"),
    ("ipiranga", "despesas.combustivel"),
    ("shell", "despesas.combustivel"),
    ("petrobras", "despesas.combustivel"),
    ("br mania", "despesas.combustivel"),
    ("ale combust", "despesas.combustivel"),

    # --- estacionamento ----------------------------------------------------
    ("estacionamento", "despesas.estacionamento"),
    ("estapar", "despesas.estacionamento"),
    ("multipark", "despesas.estacionamento"),
    ("zona azul", "despesas.estacionamento"),
    ("parking", "despesas.estacionamento"),

    # --- mercado -----------------------------------------------------------
    ("supermercado", "despesas.mercado"),
    ("mercado", "despesas.mercado"),
    ("assai", "despesas.mercado"),
    ("atacadao", "despesas.mercado"),
    ("carrefour", "despesas.mercado"),
    ("pao de acucar", "despesas.mercado"),
    ("angeloni", "despesas.mercado"),
    ("zaffari", "despesas.mercado"),
    ("hortifruti", "despesas.mercado"),

    # --- market places -----------------------------------------------------
    ("mercadolivre", "despesas.marketplaces"),
    ("mercado livre", "despesas.marketplaces"),
    ("amazon", "despesas.marketplaces"),
    ("shopee", "despesas.marketplaces"),
    ("aliexpress", "despesas.marketplaces"),
    ("magazine luiza", "despesas.marketplaces"),
    ("magalu", "despesas.marketplaces"),
    ("americanas", "despesas.marketplaces"),

    # --- assinaturas -------------------------------------------------------
    ("netflix", "despesas.assinaturas.streaming"),
    ("spotify", "despesas.assinaturas.streaming"),
    ("disney", "despesas.assinaturas.streaming"),
    ("hbo", "despesas.assinaturas.streaming"),
    ("globoplay", "despesas.assinaturas.streaming"),
    ("youtube premium", "despesas.assinaturas.streaming"),
    ("prime video", "despesas.assinaturas.streaming"),
    ("openai", "despesas.assinaturas.ia_software"),
    ("chatgpt", "despesas.assinaturas.ia_software"),
    ("anthropic", "despesas.assinaturas.ia_software"),
    ("claude", "despesas.assinaturas.ia_software"),
    ("github", "despesas.assinaturas.ia_software"),
    ("adobe", "despesas.assinaturas.ia_software"),
    ("microsoft", "despesas.assinaturas.ia_software"),
    ("google one", "despesas.assinaturas.ia_software"),
    ("icloud", "despesas.assinaturas.ia_software"),
    ("kindle", "despesas.assinaturas.livros"),
    ("livraria", "despesas.assinaturas.livros"),

    # --- saude (farmacia separada: remedio nao e dedutivel) ----------------
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
    ("laboratorio", "despesas.saude.consultas_exames"),
    ("clinica", "despesas.saude.consultas_exames"),
    ("odonto", "despesas.saude.odontologia"),

    # --- educacao ----------------------------------------------------------
    ("colegio", "despesas.educacao.escola"),
    ("escola", "despesas.educacao.escola"),
    ("mensalidade escolar", "despesas.educacao.escola"),
    ("faculdade", "despesas.educacao.faculdade"),
    ("universidade", "despesas.educacao.faculdade"),

    # --- mensais fixos -----------------------------------------------------
    ("sabesp", "despesas.mensais_fixos.agua"),
    ("copasa", "despesas.mensais_fixos.agua"),
    ("casan", "despesas.mensais_fixos.agua"),
    ("enel", "despesas.mensais_fixos.luz"),
    ("cemig", "despesas.mensais_fixos.luz"),
    ("cpfl", "despesas.mensais_fixos.luz"),
    ("celesc", "despesas.mensais_fixos.luz"),
    ("coelba", "despesas.mensais_fixos.luz"),
    ("light servicos", "despesas.mensais_fixos.luz"),
    ("comgas", "despesas.mensais_fixos.gas"),
    ("ultragaz", "despesas.mensais_fixos.gas"),
    ("vivo", "despesas.mensais_fixos.telefone"),
    ("claro", "despesas.mensais_fixos.telefone"),
    ("tim ", "despesas.mensais_fixos.telefone"),
    ("net servicos", "despesas.mensais_fixos.internet"),
    ("internet", "despesas.mensais_fixos.internet"),

    # --- condominio e anuais ----------------------------------------------
    ("condominio", "despesas.condominio_manutencao"),
    ("ipva", "despesas.anuais.ipva"),
    ("iptu", "despesas.anuais.iptu"),
    ("licenciamento", "despesas.anuais.licenciamento"),
    ("seguro", "despesas.anuais.seguros"),
    ("anuidade", "despesas.anuais.anuidades"),
    ("multa", "despesas.unicos.multas"),
    ("juros financiamento", "despesas.financiamento.juros"),
    ("amortizacao", "despesas.financiamento.amortizacao"),

    # --- faxina ------------------------------------------------------------
    ("faxina", "despesas.faxina"),
    ("diarista", "despesas.faxina"),

    # --- receitas ----------------------------------------------------------
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
