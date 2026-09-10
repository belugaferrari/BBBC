-- ============================================================================
-- Migration 0004: taxonomia definida pela familia
--
-- Substitui o catalogo generico pela arvore que o Felipe passou. Tres decisoes
-- que valem registro, porque mudam o que o sistema calcula:
--
--   1. SAUDE e EDUCACAO ganharam filhos. A lista original juntava "farmacia" e
--      "plano de saude" numa categoria so, e "escola" com "materiais" em outra.
--      Medicamento e material escolar NAO sao dedutiveis; plano, consulta e
--      mensalidade sao. Sem a separacao, o modulo de IR nao teria como saber a
--      diferenca, e a conta sairia errada nos dois sentidos.
--
--   2. INVESTIMENTOS nao e despesa. Aporte nao e dinheiro que sai da familia -
--      e dinheiro que muda de bolso. Se entrasse como despesa, o "sobrou no
--      mes" e a taxa de poupanca ficariam errados justamente para quem poupa
--      mais. Por isso vira um ramo proprio, de tipo INVESTIMENTO.
--
--   3. ANUAIS e UNICOS descrevem FREQUENCIA, nao natureza do gasto. Foram
--      criadas como pedido, mas o evolutivo trata o gasto anual diluindo-o na
--      media mensal, e o IR nao consegue classificar o que esta dentro delas.
--      Ver docs/perguntas-abertas.md.
-- ============================================================================

-- Categoria que exige comentario no lancamento: e o "unicos (com comentarios)".
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS requires_note boolean NOT NULL DEFAULT false;

-- Fora o catalogo antigo. As copias ja clonadas por familia nao sao tocadas
-- aqui: para essas existe `python -m app.cli reset-categories`, que recusa
-- apagar categoria que ja tenha lancamento.
DELETE FROM categories WHERE family_id IS NULL;

WITH cat(path, name, kind, income_nature, expense_nature,
         ir_treatment, ir_deduction_type, requires_note, icon) AS (VALUES
-- ---------------------------------------------------------------- RECEITAS --
-- Mantidas: sem elas o modulo de IR nao tem o que classificar como tributavel,
-- isento ou de tributacao exclusiva.
 ('receitas',                                'Receitas',                  'RECEITA', NULL,             NULL, 'NAO_APLICAVEL',         'NENHUMA', false, 'trending-up'),
 ('receitas.ativa_fixa',                     'Ativa Fixa',                'RECEITA', 'ATIVA_FIXA',     NULL, 'TRIBUTAVEL_TABELA',     'NENHUMA', false, 'briefcase'),
 ('receitas.ativa_fixa.pro_labore',          'Pro-labore',                'RECEITA', 'ATIVA_FIXA',     NULL, 'TRIBUTAVEL_TABELA',     'NENHUMA', false, NULL),
 ('receitas.ativa_fixa.salario',             'Salario',                   'RECEITA', 'ATIVA_FIXA',     NULL, 'TRIBUTAVEL_TABELA',     'NENHUMA', false, NULL),
 ('receitas.ativa_variavel',                 'Ativa Variavel',            'RECEITA', 'ATIVA_VARIAVEL', NULL, 'TRIBUTAVEL_TABELA',     'NENHUMA', false, 'activity'),
 ('receitas.ativa_variavel.lucros',          'Distribuicao de lucros',    'RECEITA', 'ATIVA_VARIAVEL', NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, NULL),
 ('receitas.ativa_variavel.leiloes',         'Leiloes',                   'RECEITA', 'ATIVA_VARIAVEL', NULL, 'TRIBUTAVEL_CARNE_LEAO', 'NENHUMA', false, NULL),
 ('receitas.ativa_variavel.servicos_pf',     'Servicos a pessoa fisica',  'RECEITA', 'ATIVA_VARIAVEL', NULL, 'TRIBUTAVEL_CARNE_LEAO', 'NENHUMA', false, NULL),
 ('receitas.passiva',                        'Passiva',                   'RECEITA', 'PASSIVA',        NULL, 'EXCLUSIVA_FONTE',       'NENHUMA', false, 'landmark'),
 ('receitas.passiva.renda_fixa',             'Renda fixa tributada',      'RECEITA', 'PASSIVA',        NULL, 'EXCLUSIVA_FONTE',       'NENHUMA', false, NULL),
 ('receitas.passiva.renda_fixa_isenta',      'Renda fixa isenta',         'RECEITA', 'PASSIVA',        NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, NULL),
 ('receitas.passiva.dividendos',             'Dividendos',                'RECEITA', 'PASSIVA',        NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, NULL),
 ('receitas.passiva.fii',                    'Rendimentos de FII',        'RECEITA', 'PASSIVA',        NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, NULL),
 ('receitas.passiva.ganho_capital',          'Ganho de capital',          'RECEITA', 'PASSIVA',        NULL, 'EXCLUSIVA_FONTE',       'NENHUMA', false, NULL),
 ('receitas.passiva.alugueis',               'Alugueis',                  'RECEITA', 'PASSIVA',        NULL, 'TRIBUTAVEL_CARNE_LEAO', 'NENHUMA', false, NULL),
 ('receitas.eventuais',                      'Eventuais',                 'RECEITA', 'EVENTUAL',       NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, 'gift'),
 ('receitas.eventuais.restituicao_ir',       'Restituicao de IR',         'RECEITA', 'EVENTUAL',       NULL, 'ISENTO_NAO_TRIBUTAVEL', 'NENHUMA', false, NULL),
 ('receitas.eventuais.venda_de_bens',        'Venda de bens',             'RECEITA', 'EVENTUAL',       NULL, 'EXCLUSIVA_FONTE',       'NENHUMA', false, NULL),

-- ---------------------------------------------------------------- DESPESAS --
 ('despesas',                                'Despesas',                  'DESPESA', NULL, NULL,               'NAO_APLICAVEL', 'NENHUMA', false, 'trending-down'),

 ('despesas.financiamento',                  'Financiamento',             'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'home'),
 ('despesas.condominio_manutencao',          'Condominio e manutencao',   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'wrench'),

 ('despesas.mensais_fixos',                  'Mensais fixos',             'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'plug'),
 ('despesas.mensais_fixos.agua',             'Agua',                      'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.mensais_fixos.luz',              'Luz',                       'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.mensais_fixos.gas',              'Gas',                       'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.mensais_fixos.telefone',         'Telefone',                  'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.mensais_fixos.internet',         'Internet',                  'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),

 -- Educacao: so a instrucao formal e dedutivel, e com teto anual POR pessoa.
 ('despesas.educacao',                       'Educacao',                  'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'EDUCACAO', false, 'graduation-cap'),
 ('despesas.educacao.escola',                'Escola (dedutivel)',        'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'EDUCACAO', false, NULL),
 ('despesas.educacao.faculdade',             'Faculdade e pos (dedutivel)','DESPESA', NULL, 'ESSENCIAL',       'NAO_APLICAVEL', 'EDUCACAO', false, NULL),
 ('despesas.educacao.materiais',             'Materiais (nao dedutivel)', 'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA',  false, NULL),
 ('despesas.educacao.extracurricular',       'Cursos livres (nao dedutivel)','DESPESA', NULL, 'ESSENCIAL',     'NAO_APLICAVEL', 'NENHUMA',  false, NULL),

 -- Saude: plano, consulta e exame sao dedutiveis; remedio de farmacia nao e.
 ('despesas.saude',                          'Saude',                     'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   false, 'heart-pulse'),
 ('despesas.saude.plano_de_saude',           'Plano de saude (dedutivel)','DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   false, NULL),
 ('despesas.saude.consultas_exames',         'Consultas e exames (dedutivel)','DESPESA', NULL, 'ESSENCIAL',    'NAO_APLICAVEL', 'SAUDE',   false, NULL),
 ('despesas.saude.odontologia',              'Odontologia (dedutivel)',   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   false, NULL),
 ('despesas.saude.terapias',                 'Terapias (dedutivel)',      'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   false, NULL),
 ('despesas.saude.farmacia',                 'Farmacia (nao dedutivel)',  'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, NULL),

 ('despesas.mercado',                        'Mercado',                   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'shopping-cart'),
 ('despesas.faxina',                         'Faxina',                    'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'sparkles'),
 ('despesas.criacao',                        'Criacao',                   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'baby'),

 ('despesas.combustivel',                    'Combustivel',               'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'fuel'),
 ('despesas.estacionamento',                 'Estacionamento',            'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'parking'),
 ('despesas.transportes',                    'Transportes',               'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', false, 'car'),

 ('despesas.restaurantes',                   'Restaurantes',              'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, 'utensils'),
 ('despesas.aplicativo_comida',              'Aplicativo de comida',      'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, 'bike'),
 ('despesas.marketplaces',                   'Market places',             'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, 'shopping-bag'),

 ('despesas.assinaturas',                    'Assinaturas',               'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, 'repeat'),
 ('despesas.assinaturas.streaming',          'Streaming',                 'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.assinaturas.ia_software',        'IA e softwares',            'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('despesas.assinaturas.livros',             'Livros',                    'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', false, NULL),

 ('despesas.anuais',                         'Anuais',                    'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', false, 'calendar'),
 -- 'com comentarios': o lancamento so fecha com uma explicacao escrita
 ('despesas.unicos',                         'Unicos',                    'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', true,  'asterisk'),

-- ----------------------------------------------------------- INVESTIMENTOS --
-- Ramo proprio, e nao despesa: aporte nao e dinheiro que sai da familia.
 ('investimentos',                           'Investimentos',             'INVESTIMENTO', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, 'line-chart'),
 ('investimentos.aporte',                    'Aporte',                    'INVESTIMENTO', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('investimentos.resgate',                   'Resgate',                   'INVESTIMENTO', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, NULL),

-- ---------------------------------------------------------- TRANSFERENCIAS --
 ('transferencias',                          'Transferencias',            'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, 'arrow-left-right'),
 ('transferencias.entre_contas',             'Entre contas proprias',     'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, NULL),
 ('transferencias.pagamento_cartao',         'Pagamento de fatura',       'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', false, NULL)
)
INSERT INTO categories (family_id, slug, name, kind, path, income_nature, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note, icon,
                        is_system, sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       kind::category_kind,
       path::ltree,
       income_nature::income_nature,
       expense_nature::expense_nature,
       ir_treatment::ir_treatment,
       ir_deduction_type::ir_deduction_type,
       requires_note,
       icon,
       true,
       row_number() OVER ()
FROM cat;

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);
