-- ============================================================================
-- Migration 0005: filhos de Anuais e Unicos, e a separacao juros/amortizacao
--
-- A terceira decisao da familia (separar juros de amortizacao) traz junto um
-- conceito que faltava no sistema: nem todo dinheiro que sai da conta e gasto.
--
--   * A AMORTIZACAO de um financiamento nao e despesa: e divida virando
--     patrimonio. Contada como gasto, faz o mes parecer pior do que foi.
--   * O APORTE em investimento tem exatamente a mesma natureza, e ate agora
--     estava sendo somado como saida no fluxo do mes - o mesmo erro, ja
--     presente e ainda nao percebido.
--
-- `counts_as_expense` separa os dois casos. O dinheiro continua saindo da conta
-- (o fluxo de caixa e honesto), mas a analise de consumo deixa de conta-lo.
-- ============================================================================

ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS counts_as_expense boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN categories.counts_as_expense IS
    'false quando a saida e transferencia patrimonial (amortizacao, aporte): '
    'sai da conta, mas nao e consumo.';

WITH novos(path, name, kind, expense_nature, ir_deduction_type,
           requires_note, counts_as_expense, icon) AS (VALUES
-- ------------------------------------------------------------ FINANCIAMENTO -
 ('despesas.financiamento.juros',        'Juros',                'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.financiamento.amortizacao',  'Amortizacao',          'DESPESA', 'FINANCEIRO', 'NENHUMA', false, false, NULL),
 ('despesas.financiamento.seguros_taxas','Seguros e taxas',      'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),

-- -------------------------------------------------------------------- ANUAIS -
-- Com os filhos, cada gasto anual carrega a sua propria natureza fiscal, coisa
-- que a categoria unica nao permitia.
 ('despesas.anuais.ipva',                'IPVA',                 'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.anuais.iptu',                'IPTU',                 'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.anuais.licenciamento',       'Licenciamento',        'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.anuais.seguros',             'Seguros',              'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.anuais.anuidades',           'Anuidades e taxas',    'DESPESA', 'FINANCEIRO', 'NENHUMA', false, true,  NULL),
 ('despesas.anuais.outros_anuais',       'Outros anuais',        'DESPESA', 'FINANCEIRO', 'NENHUMA', true,  true,  NULL),

-- -------------------------------------------------------------------- UNICOS -
-- Sao TIPOS de gasto avulso, e nao dominios novos: o que nao se repete.
-- Todos herdam a exigencia de comentario da categoria pai.
 ('despesas.unicos.moveis_eletro',       'Moveis e eletrodomesticos','DESPESA','ESTILO_VIDA','NENHUMA', false, true, NULL),
 ('despesas.unicos.eletronicos',         'Eletronicos',          'DESPESA', 'ESTILO_VIDA', 'NENHUMA', false, true,  NULL),
 ('despesas.unicos.presentes',           'Presentes',            'DESPESA', 'ESTILO_VIDA', 'NENHUMA', false, true,  NULL),
 ('despesas.unicos.viagens',             'Viagens',              'DESPESA', 'ESTILO_VIDA', 'NENHUMA', false, true,  NULL),
 ('despesas.unicos.reformas',            'Reformas e reparos',   'DESPESA', 'ESTILO_VIDA', 'NENHUMA', false, true,  NULL),
 ('despesas.unicos.multas',              'Multas',               'DESPESA', 'FINANCEIRO',  'NENHUMA', false, true,  NULL),
 ('despesas.unicos.outros_unicos',       'Outros',               'DESPESA', 'ESTILO_VIDA', 'NENHUMA', false, true,  NULL)
)
INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, icon, is_system, sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       kind::category_kind,
       path::ltree,
       expense_nature::expense_nature,
       'NAO_APLICAVEL'::ir_treatment,
       ir_deduction_type::ir_deduction_type,
       requires_note,
       counts_as_expense,
       icon,
       true,
       1000 + row_number() OVER ()
FROM novos;

-- Aporte e resgate mudam o bolso do dinheiro, nao o patrimonio total.
UPDATE categories
   SET counts_as_expense = false
 WHERE family_id IS NULL
   AND path <@ 'investimentos';

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND c.parent_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);
