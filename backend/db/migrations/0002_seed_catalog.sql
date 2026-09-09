-- ============================================================================
-- Migration 0002: catalogo global de categorias + parametros fiscais
-- O catalogo (family_id IS NULL) e o template clonado para cada familia nova.
-- ============================================================================

WITH cat(path, name, kind, income_nature, expense_nature, ir_treatment, ir_deduction_type, icon) AS (VALUES
-- ---------------------------------------------------------------- RECEITAS --
 ('receitas',                                   'Receitas',                      'RECEITA', NULL,              NULL, 'NAO_APLICAVEL',           'NENHUMA', 'trending-up'),
 ('receitas.ativa_fixa',                        'Ativa Fixa',                    'RECEITA', 'ATIVA_FIXA',      NULL, 'TRIBUTAVEL_TABELA',       'NENHUMA', 'briefcase'),
 ('receitas.ativa_fixa.pro_labore',             'Pro-labore',                    'RECEITA', 'ATIVA_FIXA',      NULL, 'TRIBUTAVEL_TABELA',       'NENHUMA', NULL),
 ('receitas.ativa_fixa.salario',                'Salario / CLT',                 'RECEITA', 'ATIVA_FIXA',      NULL, 'TRIBUTAVEL_TABELA',       'NENHUMA', NULL),
 ('receitas.ativa_fixa.decimo_terceiro',        '13o salario',                   'RECEITA', 'ATIVA_FIXA',      NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', NULL),

 ('receitas.ativa_variavel',                    'Ativa Variavel',                'RECEITA', 'ATIVA_VARIAVEL',  NULL, 'TRIBUTAVEL_TABELA',       'NENHUMA', 'activity'),
 ('receitas.ativa_variavel.distribuicao_lucros','Distribuicao de lucros',        'RECEITA', 'ATIVA_VARIAVEL',  NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),
 ('receitas.ativa_variavel.leiloes',            'Negocio de leiloes',            'RECEITA', 'ATIVA_VARIAVEL',  NULL, 'TRIBUTAVEL_CARNE_LEAO',   'NENHUMA', NULL),
 ('receitas.ativa_variavel.bonus_comissoes',    'Bonus e comissoes',             'RECEITA', 'ATIVA_VARIAVEL',  NULL, 'TRIBUTAVEL_TABELA',       'NENHUMA', NULL),
 ('receitas.ativa_variavel.servicos_pf',        'Servicos prestados a PF',       'RECEITA', 'ATIVA_VARIAVEL',  NULL, 'TRIBUTAVEL_CARNE_LEAO',   'NENHUMA', NULL),

 ('receitas.passiva',                           'Passiva',                       'RECEITA', 'PASSIVA',         NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', 'landmark'),
 ('receitas.passiva.renda_fixa',                'Renda fixa (CDB, Tesouro)',     'RECEITA', 'PASSIVA',         NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', NULL),
 ('receitas.passiva.renda_fixa_isenta',         'Renda fixa isenta (LCI/LCA)',   'RECEITA', 'PASSIVA',         NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),
 ('receitas.passiva.dividendos',                'Dividendos de acoes',           'RECEITA', 'PASSIVA',         NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),
 ('receitas.passiva.jcp',                       'Juros sobre capital proprio',   'RECEITA', 'PASSIVA',         NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', NULL),
 ('receitas.passiva.rendimentos_fii',           'Rendimentos de FII',            'RECEITA', 'PASSIVA',         NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),
 ('receitas.passiva.ganho_capital_acoes',       'Ganho de capital em acoes',     'RECEITA', 'PASSIVA',         NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', NULL),
 ('receitas.passiva.alugueis',                  'Alugueis',                      'RECEITA', 'PASSIVA',         NULL, 'TRIBUTAVEL_CARNE_LEAO',   'NENHUMA', NULL),

 ('receitas.eventuais',                         'Eventuais',                     'RECEITA', 'EVENTUAL',        NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', 'gift'),
 ('receitas.eventuais.restituicao_ir',          'Restituicao de IR',             'RECEITA', 'EVENTUAL',        NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),
 ('receitas.eventuais.venda_de_bens',           'Venda de bens',                 'RECEITA', 'EVENTUAL',        NULL, 'EXCLUSIVA_FONTE',         'NENHUMA', NULL),
 ('receitas.eventuais.doacoes_recebidas',       'Doacoes e presentes',           'RECEITA', 'EVENTUAL',        NULL, 'ISENTO_NAO_TRIBUTAVEL',   'NENHUMA', NULL),

-- ---------------------------------------------------------------- DESPESAS --
 ('despesas',                                   'Despesas',                      'DESPESA', NULL, NULL,               'NAO_APLICAVEL', 'NENHUMA', 'trending-down'),

 ('despesas.essenciais',                        'Essenciais',                    'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', 'home'),
 ('despesas.essenciais.moradia',                'Moradia',                       'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', 'home'),
 ('despesas.essenciais.moradia.aluguel',        'Aluguel / financiamento',       'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.condominio',     'Condominio',                    'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.energia',        'Energia eletrica',              'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.agua',           'Agua e esgoto',                 'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.gas',            'Gas',                           'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.internet',       'Internet e telefonia',          'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.manutencao',     'Manutencao e reformas',         'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.moradia.servicos_dom',   'Servicos domesticos',           'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),

 ('despesas.essenciais.alimentacao',            'Alimentacao',                   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', 'shopping-cart'),
 ('despesas.essenciais.alimentacao.supermercado','Supermercado',                 'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.alimentacao.feira',      'Feira e hortifruti',            'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.alimentacao.padaria',    'Padaria',                       'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),

 -- Saude: dedutivel sem limite (exceto medicamentos, que NAO sao dedutiveis)
 ('despesas.essenciais.saude',                  'Saude',                         'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   'heart-pulse'),
 ('despesas.essenciais.saude.plano_de_saude',   'Plano de saude',                'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   NULL),
 ('despesas.essenciais.saude.consultas',        'Consultas medicas',             'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   NULL),
 ('despesas.essenciais.saude.exames',           'Exames e internacoes',          'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   NULL),
 ('despesas.essenciais.saude.odontologia',      'Odontologia',                   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   NULL),
 ('despesas.essenciais.saude.terapias',         'Psicologia e terapias',         'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'SAUDE',   NULL),
 ('despesas.essenciais.saude.medicamentos',     'Medicamentos (nao dedutivel)',  'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),

 -- Educacao: dedutivel com teto anual POR pessoa (titular ou dependente)
 ('despesas.essenciais.educacao',               'Educacao',                      'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'EDUCACAO','graduation-cap'),
 ('despesas.essenciais.educacao.escola',        'Mensalidade escolar',           'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'EDUCACAO',NULL),
 ('despesas.essenciais.educacao.faculdade',     'Ensino superior / pos',         'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'EDUCACAO',NULL),
 ('despesas.essenciais.educacao.material',      'Material escolar (nao dedutivel)','DESPESA', NULL, 'ESSENCIAL',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.educacao.extracurricular','Cursos livres e idiomas (nao dedutivel)','DESPESA', NULL, 'ESSENCIAL','NAO_APLICAVEL','NENHUMA', NULL),

 ('despesas.essenciais.transporte',             'Transporte',                    'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', 'car'),
 ('despesas.essenciais.transporte.combustivel', 'Combustivel',                   'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.transporte.manutencao',  'Manutencao do veiculo',         'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.transporte.apps',        'Apps de transporte',            'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.essenciais.transporte.estacionamento','Estacionamento e pedagio',    'DESPESA', NULL, 'ESSENCIAL',        'NAO_APLICAVEL', 'NENHUMA', NULL),

 ('despesas.estilo_vida',                       'Estilo de Vida',                'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'sparkles'),
 ('despesas.estilo_vida.restaurantes',          'Restaurantes e delivery',       'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'utensils'),
 ('despesas.estilo_vida.lazer',                 'Lazer',                         'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'film'),
 ('despesas.estilo_vida.lazer.streaming',       'Streaming e assinaturas',       'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.estilo_vida.lazer.eventos',         'Eventos e passeios',            'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.estilo_vida.hobbies',               'Hobbies',                       'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'puzzle'),
 ('despesas.estilo_vida.hobbies.impressao_3d',  'Impressao 3D (Bambu Lab)',      'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.estilo_vida.viagens',               'Viagens',                       'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'plane'),
 ('despesas.estilo_vida.compras',               'Compras pessoais',              'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'shopping-bag'),
 ('despesas.estilo_vida.compras.vestuario',     'Vestuario',                     'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.estilo_vida.compras.eletronicos',   'Eletronicos',                   'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.estilo_vida.criancas',              'Criancas',                      'DESPESA', NULL, 'ESTILO_VIDA',      'NAO_APLICAVEL', 'NENHUMA', 'baby'),

 ('despesas.metas_projetos',                    'Metas & Projetos',              'DESPESA', NULL, 'METAS_PROJETOS',   'NAO_APLICAVEL', 'NENHUMA', 'target'),
 ('despesas.metas_projetos.fundo_disney',       'Fundo viagem Disney',           'DESPESA', NULL, 'METAS_PROJETOS',   'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.metas_projetos.reserva',            'Reserva de emergencia',         'DESPESA', NULL, 'METAS_PROJETOS',   'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.metas_projetos.aportes',            'Aportes em investimentos',      'DESPESA', NULL, 'METAS_PROJETOS',   'NAO_APLICAVEL', 'NENHUMA', NULL),

 ('despesas.financeiro',                        'Financeiro',                    'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', 'banknote'),
 ('despesas.financeiro.impostos',               'Impostos',                      'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.impostos.irpf',          'IRPF (carne-leao / DARF)',      'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.impostos.ipva',          'IPVA',                          'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.impostos.iptu',          'IPTU',                          'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.seguros',                'Seguros',                       'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', 'shield'),
 ('despesas.financeiro.seguros.vida',           'Seguro de vida',                'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.seguros.veiculo',        'Seguro do veiculo',             'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.seguros.residencial',    'Seguro residencial',            'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.tarifas',                'Tarifas e juros',               'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.previdencia',            'Previdencia',                   'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('despesas.financeiro.previdencia.inss',       'INSS / previdencia oficial',    'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'PREVIDENCIA_OFICIAL', NULL),
 ('despesas.financeiro.previdencia.pgbl',       'PGBL',                          'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'PREVIDENCIA_PRIVADA_PGBL', NULL),
 ('despesas.financeiro.pensao',                 'Pensao alimenticia judicial',   'DESPESA', NULL, 'FINANCEIRO',       'NAO_APLICAVEL', 'PENSAO_ALIMENTICIA', NULL),

-- --------------------------------------------------- TRANSFERENCIAS / INVEST --
 ('transferencias',                             'Transferencias',                'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', 'arrow-left-right'),
 ('transferencias.entre_contas',                'Entre contas proprias',         'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('transferencias.pagamento_cartao',            'Pagamento de fatura',           'TRANSFERENCIA', NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('investimentos',                              'Investimentos',                 'INVESTIMENTO',  NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', 'line-chart'),
 ('investimentos.aporte',                       'Aporte',                        'INVESTIMENTO',  NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', NULL),
 ('investimentos.resgate',                      'Resgate',                       'INVESTIMENTO',  NULL, NULL, 'NAO_APLICAVEL', 'NENHUMA', NULL)
)
INSERT INTO categories (family_id, slug, name, kind, path, income_nature, expense_nature,
                        ir_treatment, ir_deduction_type, icon, is_system, sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       kind::category_kind,
       path::ltree,
       income_nature::income_nature,
       expense_nature::expense_nature,
       ir_treatment::ir_treatment,
       ir_deduction_type::ir_deduction_type,
       icon,
       true,
       row_number() OVER ()
FROM cat;

-- amarra os pais pelo caminho materializado
UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);

-- ---------------------------------------------------------------------------
-- Parametros fiscais. TODOS os numeros ficam em tabela, nunca no codigo.
-- status = 'PROVISORIO' ate serem conferidos contra a IN/lei do ano-calendario.
-- ---------------------------------------------------------------------------
INSERT INTO tax_years (year, status, source_reference) VALUES
 (2025, 'PROVISORIO', 'Tabela progressiva vigente em 2025 - conferir IN RFB do ano-calendario'),
 (2026, 'PROVISORIO', 'Lei 15.270/2025 (isencao ate R$ 5.000/mes + redutor) - conferir regulamentacao');

-- Tabela progressiva MENSAL 2025 (retencao na fonte / carne-leao)
INSERT INTO tax_brackets (year, scope, min_base, max_base, rate, deduction, valid_from) VALUES
 (2025, 'MENSAL',      0.00,  2259.20, 0.0000,   0.00, DATE '2025-01-01'),
 (2025, 'MENSAL',   2259.21,  2826.65, 0.0750, 169.44, DATE '2025-01-01'),
 (2025, 'MENSAL',   2826.66,  3751.05, 0.1500, 381.44, DATE '2025-01-01'),
 (2025, 'MENSAL',   3751.06,  4664.68, 0.2250, 662.77, DATE '2025-01-01'),
 (2025, 'MENSAL',   4664.69,     NULL, 0.2750, 896.00, DATE '2025-01-01');

-- Tabela progressiva ANUAL 2025 (ajuste na declaracao) = mensal x 12
INSERT INTO tax_brackets (year, scope, min_base, max_base, rate, deduction, valid_from) VALUES
 (2025, 'ANUAL',       0.00,  27110.40, 0.0000,     0.00, DATE '2025-01-01'),
 (2025, 'ANUAL',   27110.41,  33919.80, 0.0750,  2033.28, DATE '2025-01-01'),
 (2025, 'ANUAL',   33919.81,  45012.60, 0.1500,  4577.28, DATE '2025-01-01'),
 (2025, 'ANUAL',   45012.61,  55976.16, 0.2250,  7953.24, DATE '2025-01-01'),
 (2025, 'ANUAL',   55976.17,      NULL, 0.2750, 10752.00, DATE '2025-01-01');

INSERT INTO tax_parameters (year, key, value, unit, description) VALUES
 (2025, 'DEDUCAO_DEPENDENTE_ANUAL',      2275.08, 'BRL', 'Deducao anual por dependente'),
 (2025, 'LIMITE_EDUCACAO_ANUAL',         3561.50, 'BRL', 'Teto anual de instrucao por pessoa (titular ou dependente)'),
 (2025, 'DESCONTO_SIMPLIFICADO_PCT',      0.2000, 'PCT', 'Percentual do desconto simplificado sobre rendimentos tributaveis'),
 (2025, 'DESCONTO_SIMPLIFICADO_TETO',   16754.34, 'BRL', 'Teto do desconto simplificado'),
 (2025, 'DEDUCAO_SIMPLIFICADA_MENSAL',    564.80, 'BRL', 'Desconto simplificado mensal na fonte'),
 (2025, 'LIMITE_PGBL_PCT',                0.1200, 'PCT', 'Limite de deducao de PGBL sobre a renda bruta tributavel'),
 (2025, 'ISENCAO_VENDA_ACOES_MENSAL',   20000.00, 'BRL', 'Isencao mensal de vendas de acoes no mercado a vista'),
 (2025, 'ALIQUOTA_SWING_TRADE',           0.1500, 'PCT', 'Aliquota sobre ganho liquido em operacoes comuns'),
 (2025, 'ALIQUOTA_DAY_TRADE',             0.2000, 'PCT', 'Aliquota sobre ganho liquido em day trade'),
 (2025, 'ALIQUOTA_GANHO_FII',             0.2000, 'PCT', 'Aliquota sobre ganho de capital em FII');

-- 2026: as faixas abaixo sao uma COPIA das de 2025, apenas para o sistema nao
-- ficar sem tabela. Elas NAO refletem a regra nova (isencao ampliada +
-- tributacao minima) e precisam ser substituidas pela tabela oficial antes de
-- o ano sair do status PROVISORIO. Ver docs/perguntas-abertas.md.
INSERT INTO tax_brackets (year, scope, min_base, max_base, rate, deduction, valid_from)
SELECT 2026, scope, min_base, max_base, rate, deduction, DATE '2026-01-01'
  FROM tax_brackets
 WHERE year = 2025;

-- Demais parametros de 2026.
INSERT INTO tax_parameters (year, key, value, unit, description) VALUES
 (2026, 'ISENCAO_MENSAL',              5000.00, 'BRL', 'Faixa de isencao mensal (Lei 15.270/2025)'),
 (2026, 'REDUTOR_LIMITE_SUPERIOR',     7350.00, 'BRL', 'Renda mensal ate a qual o redutor progressivo se aplica'),
 (2026, 'DEDUCAO_DEPENDENTE_ANUAL',    2275.08, 'BRL', 'Deducao anual por dependente'),
 (2026, 'LIMITE_EDUCACAO_ANUAL',       3561.50, 'BRL', 'Teto anual de instrucao por pessoa'),
 (2026, 'DESCONTO_SIMPLIFICADO_PCT',    0.2000, 'PCT', 'Percentual do desconto simplificado'),
 (2026, 'DESCONTO_SIMPLIFICADO_TETO', 16754.34, 'BRL', 'Teto do desconto simplificado');

INSERT INTO institutions (name) VALUES
 ('Manual') ON CONFLICT DO NOTHING;
