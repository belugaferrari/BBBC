-- ============================================================================
-- Migration 0014: os nomes das categorias escritos em portugues de verdade
--
-- "Nao achei nas categorias de entrada de dinheiro: doacao."
--
-- A categoria existia. O nome dela e que estava escrito "Doacoes recebidas", sem
-- cedilha e sem til - como todo o resto do catalogo, que nasceu em SQL ASCII.
-- Isso quebra DUAS coisas, e a segunda e invisivel ate alguem procurar:
--
--   1. a leitura. "Condominio", "Saude", "Agua", "Cafe", "Moveis e
--      eletrodomesticos" aparecem assim na tela, o dia inteiro, nas telas que a
--      familia mais olha;
--   2. a BUSCA. Procurar "doacao" (que o aplicativo normaliza tirando os
--      acentos) nao encontra "doacoes": "doacao" nao e pedaco de "doacoes".
--      Quem procura pelo singular nao acha o plural, e conclui que a categoria
--      nao existe - que foi exatamente o que aconteceu.
--
-- O nome e o unico jeito de achar uma categoria na tela. Ele merece estar certo.
--
-- O `slug` e o `path` ficam como estao, sem acento: sao identidade, nao texto de
-- tela. Trocar `path` exigiria reescrever o caminho de todos os descendentes e
-- de tudo que aponta para eles - e ninguem nunca ve esse campo.
-- ============================================================================

WITH certo(caminho, nome) AS (VALUES
 -- despesas
 ('despesas.condominio',                   'Condomínio'),
 ('despesas.criacao',                      'Criação'),
 ('despesas.educacao',                     'Educação'),
 ('despesas.educacao.faculdade',           'Faculdade e pós'),
 ('despesas.financiamentos.amortizacao',   'Amortização'),
 ('despesas.gastos_mensais.agua',          'Água'),
 ('despesas.gastos_mensais.gas',           'Gás'),
 ('despesas.gastos_unicos',                'Gastos únicos'),
 ('despesas.gastos_unicos.eletronicos',    'Eletrônicos'),
 ('despesas.gastos_unicos.moveis_eletro',  'Móveis e eletrodomésticos'),
 ('despesas.restaurantes.cafe',            'Café'),
 ('despesas.saude',                        'Saúde'),
 ('despesas.saude.farmacia',               'Farmácia'),
 ('despesas.saude.plano_de_saude',         'Plano de saúde'),
 ('despesas.transporte.manutencao',        'Manutenção do carro'),
 ('despesas.transporte.pedagio_tag',       'Pedágio e tag'),
 -- receitas
 ('receitas.ativa_fixa',                   'Ativa fixa'),
 ('receitas.ativa_fixa.pro_labore',        'Pró-labore'),
 ('receitas.ativa_fixa.salario',           'Salário'),
 ('receitas.ativa_variavel',               'Ativa variável'),
 ('receitas.ativa_variavel.leiloes',       'Leilões'),
 ('receitas.ativa_variavel.lucros',        'Distribuição de lucros'),
 ('receitas.ativa_variavel.servicos_pf',   'Serviços a pessoa física'),
 ('receitas.doacoes',                      'Doações recebidas'),
 ('receitas.doacoes.outras',               'Outras doações'),
 ('receitas.eventuais.adiantamento_socio', 'Adiantamento de sócio'),
 ('receitas.eventuais.restituicao_ir',     'Restituição de IR'),
 ('receitas.passiva.alugueis',             'Aluguéis'),
 -- transferencias e empresa
 ('transferencias',                        'Transferências'),
 ('transferencias.entre_contas',           'Entre contas próprias')
)
UPDATE categories c
   SET name = certo.nome
  FROM certo
 WHERE c.path = certo.caminho::ltree
   -- So troca o que ainda esta sem acento. Se a familia renomeou a categoria
   -- (direito que ela tem), o nome dela fica: o acento nao vale desfazer uma
   -- escolha de quem usa.
   --
   -- A comparacao ignora maiusculas porque duas destas tambem estao com a
   -- inicial errada no catalogo antigo ("Ativa Fixa", "Ativa Variavel"). Sem o
   -- lower(), elas passariam batido - e o guarda continua fazendo o seu papel,
   -- porque um nome escolhido por ele difere nas LETRAS, nao so na caixa.
   AND lower(c.name) = lower(translate(
        certo.nome,
        'áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ',
        'aaaaeeiooouucAAAAEEIOOOUUC'
   ));
