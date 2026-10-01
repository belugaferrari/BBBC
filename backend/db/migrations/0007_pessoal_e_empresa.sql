-- ============================================================================
-- Migration 0007: separar o que e meu do que e da empresa
--
-- O problema real: a conta da empresa as vezes paga conta pessoal, e a conta
-- pessoal as vezes paga conta da empresa. Hoje isso se resolve a mao, no Excel.
--
-- Duas armadilhas que esta migration existe para evitar:
--
--   1. A empresa paga a escola da filha. Lancar SO a despesa faz o caixa da
--      familia cair R$ 3.000 por um gasto que nao saiu do bolso dela - o saldo
--      fica errado, e a previsao herda o erro. O gasto e real e tem que contar
--      na categoria; o dinheiro e que veio de fora. Por isso o par: a despesa
--      na categoria certa MAIS a entrada que a cobre.
--
--   2. Eu pago um fornecedor da empresa com meu cartao. O dinheiro sai mesmo,
--      entao o caixa cai de verdade - mas isso NAO e consumo da familia, e sim
--      um credito a receber. Contado como gasto, inflaria a categoria e o teto.
--      Vai para um ramo com counts_as_expense = false, o mesmo mecanismo que ja
--      separa amortizacao e aporte de despesa (migration 0005).
-- ============================================================================

-- Conta da empresa: o extrato dela entra para ser triado, nao para virar
-- patrimonio da familia. O saldo e da pessoa juridica.
ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS is_business boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN accounts.is_business IS
    'true para conta da empresa: o saldo nao entra no patrimonio da familia, e '
    'a importacao do extrato pede triagem linha a linha.';

DO $$ BEGIN
    CREATE TYPE socio_flow AS ENUM (
        'PESSOAL_VIA_EMPRESA',   -- conta minha, paga pela empresa
        'EMPRESA_VIA_PESSOAL'    -- conta da empresa, paga com meu dinheiro
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS socio_flow socio_flow,
    -- Quando a pendencia foi acertada. NULL com socio_flow preenchido = em
    -- aberto; e dai que sai a lista de "a empresa me deve".
    ADD COLUMN IF NOT EXISTS settled_on date;

COMMENT ON COLUMN transactions.socio_flow IS
    'Marca o dinheiro que cruzou a fronteira entre pessoa fisica e juridica. '
    'NULL na esmagadora maioria dos lancamentos.';

-- A lista de pendencias e consultada por familia; o indice parcial so cobre as
-- linhas que de fato cruzaram a fronteira e ainda nao foram acertadas.
CREATE INDEX IF NOT EXISTS transactions_socio_em_aberto_idx
    ON transactions (family_id, booked_on)
 WHERE socio_flow IS NOT NULL AND settled_on IS NULL;

-- ---------------------------------------------------------------- Categorias

-- A contrapartida de uma conta pessoal paga pela empresa precisa de categoria
-- propria, porque o IR de cada uma e diferente: pro-labore entra na tabela
-- progressiva, lucro e isento, e adiantamento nao e renda - e divida a acertar.
-- Pro-labore e lucros ja existem desde a 0004; falta o adiantamento.
WITH novos(path, name, kind, income_nature, ir_treatment, icon) AS (VALUES
    ('receitas.eventuais.adiantamento_socio', 'Adiantamento de socio',
     'RECEITA'::category_kind, 'EVENTUAL'::income_nature,
     -- Nao e renda: e saldo em conta-corrente de socio, a acertar depois como
     -- pro-labore ou lucro. Classificar como tributavel aqui inventaria imposto.
     'NAO_APLICAVEL'::ir_treatment, 'handshake')
)
INSERT INTO categories (family_id, parent_id, slug, name, kind, income_nature,
                        ir_treatment, icon, is_system)
SELECT NULL,
       (SELECT id FROM categories WHERE family_id IS NULL AND path = subltree(n.path::ltree, 0, 2)),
       subpath(n.path::ltree, nlevel(n.path::ltree) - 1)::text,
       n.name, n.kind, n.income_nature, n.ir_treatment, n.icon, true
  FROM novos n
 WHERE NOT EXISTS (SELECT 1 FROM categories c WHERE c.family_id IS NULL AND c.path = n.path::ltree);

-- O ramo do dinheiro que sai por conta da empresa. counts_as_expense = false:
-- sai da conta (o caixa e honesto) mas nao e consumo da familia.
WITH raiz AS (
    INSERT INTO categories (family_id, parent_id, slug, name, kind,
                            expense_nature, counts_as_expense, icon, is_system)
    SELECT NULL, NULL, 'conta_corrente_socio', 'Conta-corrente da empresa',
           'DESPESA'::category_kind, 'FINANCEIRO'::expense_nature, false,
           'briefcase', true
     WHERE NOT EXISTS (SELECT 1 FROM categories
                        WHERE family_id IS NULL AND path = 'conta_corrente_socio'::ltree)
    RETURNING id
)
INSERT INTO categories (family_id, parent_id, slug, name, kind,
                        expense_nature, counts_as_expense, icon, is_system)
SELECT NULL,
       COALESCE((SELECT id FROM raiz),
                (SELECT id FROM categories
                  WHERE family_id IS NULL AND path = 'conta_corrente_socio'::ltree)),
       'pago_por_mim', 'Paguei pela empresa',
       'DESPESA'::category_kind, 'FINANCEIRO'::expense_nature, false,
       'briefcase', true
 WHERE NOT EXISTS (SELECT 1 FROM categories
                    WHERE family_id IS NULL AND path = 'conta_corrente_socio.pago_por_mim'::ltree);
