-- ============================================================================
-- Migration 0009: a taxonomia de despesa passa a ser a do Felipe
--
-- Ate aqui a arvore era a que eu propus. Ele usa outra, ha anos, no Excel - e a
-- dele e que manda, por dois motivos praticos. O primeiro: a categoria e a
-- unidade de meta ("quanto posso gastar em Mercado este mes"), e meta so faz
-- sentido no recorte em que a pessoa pensa. O segundo: ele vai conferir os
-- numeros contra as planilhas antigas, e nao da para comparar o que esta
-- agrupado de forma diferente.
--
-- As quinze da lista dele, na ordem em que ele as escreveu:
--
--   Gastos mensais, Condominio, Financiamentos, Educacao, Saude, Transporte,
--   Mercado, Restaurantes, Market places, Delivery de comida, Limpeza,
--   Gastos anuais, Gastos unicos, Criacao, Cla PJ
--
-- Quase tudo ja existia, espalhado de outro jeito: 'Combustivel',
-- 'Estacionamento' e 'Transportes' eram tres categorias soltas de primeiro
-- nivel, e agora sao filhas de Transporte, que e o lugar onde ele poe a meta.
-- 'Assinaturas' desceu para dentro de Gastos mensais, que e como ele conta.
-- 'Faxina' virou 'Limpeza' e 'Aplicativo de comida' virou 'Delivery de comida',
-- os nomes dele. 'Cla PJ' e nova.
--
-- O terceiro nivel sobrevive onde ele citou exemplos ("luz, agua, telefone...")
-- ou onde a natureza fiscal difere entre as filhas: plano de saude e dedutivel
-- e farmacia nao, e isso tem de continuar separado ou a projecao de IR erra.
-- A meta fica no segundo nivel e soma a subarvore inteira.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. Pagamento de fatura e transferencia de bolso, nao consumo
-- --------------------------------------------------------------------------
-- A compra no cartao JA e a despesa, e ela e lancada no dia em que acontece.
-- Quando a fatura e paga, o dinheiro sai da conta corrente para o cartao - se
-- esse pagamento contasse como gasto, cada compra no cartao seria contada duas
-- vezes: uma na compra, outra na fatura. O mes dobraria de tamanho.
--
-- `counts_as_expense = false` e o que impede isso. Estava `true` na arvore toda
-- de transferencias desde a 0004, e seria a primeira coisa a estourar quando o
-- extrato da conta corrente chegasse com "PAGAMENTO FATURA CARTAO" nele.
UPDATE categories
   SET counts_as_expense = false
 WHERE path <@ 'transferencias'::ltree
   AND counts_as_expense;

COMMENT ON COLUMN categories.counts_as_expense IS
    'false quando a saida nao e consumo: amortizacao e aporte (divida ou '
    'dinheiro virando patrimonio) e pagamento de fatura (a despesa foi a '
    'compra, no dia dela - contar a fatura tambem dobraria o mes).';

-- --------------------------------------------------------------------------
-- 2. A arvore de despesa, refeita no catalogo global
-- --------------------------------------------------------------------------
-- O catalogo global (family_id IS NULL) e o molde do qual cada familia recebe
-- a sua copia. Refazer o molde nao mexe em copia nenhuma - o passo 3 cuida
-- disso, e so onde for seguro.
DELETE FROM categories
 WHERE family_id IS NULL
   AND path <@ 'despesas'::ltree
   AND path <> 'despesas'::ltree;

WITH nova(path, name, expense_nature, ir_deduction_type, requires_note,
          counts_as_expense, icon) AS (VALUES
-- ---------------------------------------------------------- GASTOS MENSAIS --
 ('despesas.gastos_mensais',              'Gastos mensais',       'ESSENCIAL',   'NENHUMA',  false, true,  'calendar-clock'),
 ('despesas.gastos_mensais.luz',          'Luz',                  'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.agua',         'Agua',                 'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.gas',          'Gas',                  'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.telefone',     'Telefone',             'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.internet',     'Internet',             'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.assinaturas',  'Assinaturas',          'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_mensais.assinaturas.streaming',   'Streaming',        'ESTILO_VIDA', 'NENHUMA', false, true, NULL),
 ('despesas.gastos_mensais.assinaturas.softwares',   'IA e softwares',   'ESTILO_VIDA', 'NENHUMA', false, true, NULL),
 ('despesas.gastos_mensais.assinaturas.livros',      'Livros',           'ESTILO_VIDA', 'NENHUMA', false, true, NULL),

-- -------------------------------------------------------------- CONDOMINIO --
-- Mensal como os de cima, mas contado a parte por escolha dele: e o maior dos
-- fixos e ele quer ver o numero sozinho, sem diluir no bolo.
 ('despesas.condominio',                  'Condominio',           'ESSENCIAL',   'NENHUMA',  false, true,  'building'),

-- ---------------------------------------------------------- FINANCIAMENTOS --
 ('despesas.financiamentos',              'Financiamentos',       'FINANCEIRO',  'NENHUMA',  false, true,  'bank'),
 ('despesas.financiamentos.juros',        'Juros',                'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 -- amortizacao nao e consumo: e divida virando patrimonio
 ('despesas.financiamentos.amortizacao',  'Amortizacao',          'FINANCEIRO',  'NENHUMA',  false, false, NULL),
 ('despesas.financiamentos.seguros_taxas','Seguros e taxas',      'FINANCEIRO',  'NENHUMA',  false, true,  NULL),

-- ---------------------------------------------------------------- EDUCACAO --
 -- O pai carrega o tipo de deducao para o caso de alguem lancar direto nele,
 -- sem descer na subcategoria. As filhas que NAO sao dedutiveis (material
 -- escolar, farmacia) dizem isso por conta propria, logo abaixo - cada linha
 -- usa o tipo da sua propria categoria, nao o do pai.
 ('despesas.educacao',                    'Educacao',             'ESSENCIAL',   'EDUCACAO', false, true,  'school'),
 ('despesas.educacao.escola',             'Escola',               'ESSENCIAL',   'EDUCACAO', false, true,  NULL),
 ('despesas.educacao.faculdade',          'Faculdade e pos',      'ESSENCIAL',   'EDUCACAO', false, true,  NULL),
 -- material escolar nao e dedutivel; so a instrucao e
 ('despesas.educacao.materiais',          'Materiais',            'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.educacao.cursos_livres',      'Cursos livres',        'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),

-- ------------------------------------------------------------------- SAUDE --
 ('despesas.saude',                       'Saude',                'ESSENCIAL',   'SAUDE',    false, true,  'heart-pulse'),
 ('despesas.saude.plano_de_saude',        'Plano de saude',       'ESSENCIAL',   'SAUDE',    false, true,  NULL),
 ('despesas.saude.consultas_exames',      'Consultas e exames',   'ESSENCIAL',   'SAUDE',    false, true,  NULL),
 ('despesas.saude.odontologia',           'Odontologia',          'ESSENCIAL',   'SAUDE',    false, true,  NULL),
 ('despesas.saude.terapias',              'Terapias',             'ESSENCIAL',   'SAUDE',    false, true,  NULL),
 -- remedio de farmacia nao entra na deducao, por mais que doa
 ('despesas.saude.farmacia',              'Farmacia',             'ESSENCIAL',   'NENHUMA',  false, true,  NULL),

-- --------------------------------------------------------------- TRANSPORTE -
 ('despesas.transporte',                  'Transporte',           'ESSENCIAL',   'NENHUMA',  false, true,  'car'),
 ('despesas.transporte.gasolina',         'Gasolina',             'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.transporte.aplicativo',       'Transporte por aplicativo', 'ESSENCIAL', 'NENHUMA', false, true, NULL),
 ('despesas.transporte.estacionamento',   'Estacionamento',       'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.transporte.pedagio_tag',      'Pedagio e tag',        'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.transporte.manutencao',       'Manutencao do carro',  'ESSENCIAL',   'NENHUMA',  false, true,  NULL),

-- ----------------------------------------------------------------- MERCADO --
 ('despesas.mercado',                     'Mercado',              'ESSENCIAL',   'NENHUMA',  false, true,  'shopping-cart'),

-- ------------------------------------------------------------- RESTAURANTES -
 ('despesas.restaurantes',                'Restaurantes',         'ESTILO_VIDA', 'NENHUMA',  false, true,  'utensils'),
 ('despesas.restaurantes.restaurante',    'Restaurante',          'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.restaurantes.padaria',        'Padaria e lanchonete', 'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.restaurantes.cafe',           'Cafe',                 'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),

-- ------------------------------------------------------------ MARKET PLACES -
 ('despesas.market_places',               'Market places',        'ESTILO_VIDA', 'NENHUMA',  false, true,  'package'),

-- -------------------------------------------------------- DELIVERY DE COMIDA
-- Separado de Restaurantes de proposito: sao dois habitos diferentes, com
-- tetos diferentes, e misturar os dois esconde qual deles cresceu.
 ('despesas.delivery',                    'Delivery de comida',   'ESTILO_VIDA', 'NENHUMA',  false, true,  'bike'),

-- ----------------------------------------------------------------- LIMPEZA --
 ('despesas.limpeza',                     'Limpeza',              'ESSENCIAL',   'NENHUMA',  false, true,  'spray-can'),
 ('despesas.limpeza.diarista',            'Diarista',             'ESSENCIAL',   'NENHUMA',  false, true,  NULL),

-- ----------------------------------------------------------- GASTOS ANUAIS --
 ('despesas.gastos_anuais',               'Gastos anuais',        'FINANCEIRO',  'NENHUMA',  false, true,  'calendar'),
 ('despesas.gastos_anuais.ipva',          'IPVA',                 'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_anuais.iptu',          'IPTU',                 'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_anuais.licenciamento', 'Licenciamento',        'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_anuais.seguro_carro',  'Seguro do carro',      'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_anuais.anuidades',     'Anuidades e taxas',    'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_anuais.outros_anuais', 'Outros anuais',        'FINANCEIRO',  'NENHUMA',  true,  true,  NULL),

-- ----------------------------------------------------------- GASTOS UNICOS --
-- "coisas nao previstas que acontecem no mes", nas palavras dele. Exige
-- comentario, e a exigencia desce para as filhas: daqui a seis meses ninguem
-- lembra o que foi um gasto avulso de R$ 3.400.
 ('despesas.gastos_unicos',               'Gastos unicos',        'ESTILO_VIDA', 'NENHUMA',  true,  true,  'sparkles'),
 ('despesas.gastos_unicos.moveis_eletro', 'Moveis e eletrodomesticos', 'ESTILO_VIDA', 'NENHUMA', false, true, NULL),
 ('despesas.gastos_unicos.eletronicos',   'Eletronicos',          'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_unicos.presentes',     'Presentes',            'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_unicos.viagens',       'Viagens',              'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_unicos.reformas',      'Reformas e reparos',   'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_unicos.multas',        'Multas',               'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.gastos_unicos.outros_unicos', 'Outros',               'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),

-- ----------------------------------------------------------------- CRIACAO --
 ('despesas.criacao',                     'Criacao',              'ESSENCIAL',   'NENHUMA',  false, true,  'baby'),
 ('despesas.criacao.brinquedos',          'Brinquedos',           'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),
 ('despesas.criacao.roupas',              'Roupas',               'ESSENCIAL',   'NENHUMA',  false, true,  NULL),
 ('despesas.criacao.atividades',          'Atividades',           'ESTILO_VIDA', 'NENHUMA',  false, true,  NULL),

-- ------------------------------------------------------------------ CLA PJ --
-- Custo de manter a pessoa juridica da Clarissa de pe. Sai do bolso da familia,
-- entao e despesa daqui - mas num balde proprio, para nao se misturar com o
-- consumo da casa quando ele for olhar onde o dinheiro foi.
 ('despesas.cla_pj',                      'Cla PJ',               'FINANCEIRO',  'NENHUMA',  false, true,  'briefcase'),
 ('despesas.cla_pj.nota_fiscal',          'Nota fiscal',          'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.cla_pj.contabilidade',        'Contabilidade',        'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.cla_pj.darf',                 'DARF e impostos',      'FINANCEIRO',  'NENHUMA',  false, true,  NULL),
 ('despesas.cla_pj.outros_pj',            'Outros da PJ',         'FINANCEIRO',  'NENHUMA',  false, true,  NULL)
)
INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, icon, is_system, sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       'DESPESA'::category_kind,
       path::ltree,
       expense_nature::expense_nature,
       'NAO_APLICAVEL'::ir_treatment,
       ir_deduction_type::ir_deduction_type,
       requires_note,
       counts_as_expense,
       icon,
       true,
       -- 1000 + a ordem da lista: deixa a arvore de despesa depois das outras
       -- raizes e preserva a ordem em que ele escreveu as categorias
       1000 + row_number() OVER ()
FROM nova;

-- Pais amarrados pelo path, depois da insercao em lote - e como o resto do
-- catalogo e montado desde a 0004.
UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);

-- --------------------------------------------------------------------------
-- 3. Familias que ainda nao tem historico recebem a arvore nova
-- --------------------------------------------------------------------------
-- Quem ja classificou lancamento ou ja pos meta fica como esta: apagar a
-- categoria por baixo de um gasto o transformaria em gasto solto, e o estrago
-- so apareceria no fechamento do mes. Para essas existe o caminho manual,
-- `python -m app.cli reset-categories`, que recusa pelo mesmo motivo - e, no
-- aplicativo, a tela de categorias, onde da para renomear e criar uma a uma.
--
-- Em tres comandos de conjunto, e nao num laco por familia. A primeira versao
-- percorria familia por familia, e cada volta do laco fazia um UPDATE que
-- varria a tabela inteira de categorias para reamarrar os pais - com 800
-- familias no banco de testes isso virou quadratico e a migration passou de tres
-- minutos sem dar sinal de vida. O custo aqui nao depende do numero de familias.

-- A reamarracao de pai procura o pai pelo caminho, dentro da mesma familia. Sem
-- este indice a busca e uma varredura da tabela toda, e e ela que travava.
CREATE INDEX IF NOT EXISTS categories_family_path_idx
    ON categories (family_id, path);

CREATE TEMP TABLE familias_limpas AS
SELECT f.id
  FROM families f
 WHERE NOT EXISTS (
           SELECT 1 FROM transactions t
             JOIN categories c ON c.id = t.category_id
            WHERE c.family_id = f.id
       )
   AND NOT EXISTS (SELECT 1 FROM budget_caps b WHERE b.family_id = f.id);

-- O molde copiado para fora da tabela: o INSERT abaixo le daqui, e nao de
-- `categories`, para nao haver duvida sobre ele enxergar as proprias linhas.
CREATE TEMP TABLE molde AS
SELECT * FROM categories WHERE family_id IS NULL;

DELETE FROM categories WHERE family_id IN (SELECT id FROM familias_limpas);

INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        expense_nature, ir_treatment, ir_deduction_type,
                        requires_note, counts_as_expense, icon, color,
                        is_system, sort_order)
SELECT fl.id, m.slug, m.name, m.kind, m.path, m.income_nature, m.expense_nature,
       m.ir_treatment, m.ir_deduction_type, m.requires_note, m.counts_as_expense,
       m.icon, m.color, m.is_system, m.sort_order
  FROM familias_limpas fl
 CROSS JOIN molde m;

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IN (SELECT id FROM familias_limpas)
   AND p.family_id = c.family_id
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);

DROP TABLE familias_limpas;
DROP TABLE molde;
