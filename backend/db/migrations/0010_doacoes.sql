-- ============================================================================
-- Migration 0010: dinheiro que entra e nao e renda
--
-- Os sogros depositam todo mes para pagar a escola das meninas. Esse dinheiro
-- entra na conta, mas nao e renda da familia - e tratar como se fosse estraga
-- tres numeros de uma vez: a renda do mes fica maior do que e, a taxa de
-- poupanca fica irreal, e a projecao dos proximos meses passa a contar com um
-- dinheiro que depende da vontade de outra pessoa.
--
-- Tres pecas entram aqui:
--
--   1. `counts_as_income`, o espelho do `counts_as_expense` do lado da receita:
--      entrou na conta, mas nao e renda.
--
--   2. `donors`, porque o limite de isencao do ITCMD e POR DOADOR e por ano.
--      Vera e Jose depositando metade cada um nao e a mesma coisa que um deles
--      depositando tudo, e so da para saber isso guardando quem deu.
--
--   3. a destinacao da doacao. Doacao com destino ("isto e para a escola")
--      permite abater do consumo da familia exatamente o que ela cobriu - sem
--      isso, a escola apareceria inteira como gasto da casa e a taxa de
--      poupanca ficaria pior do que a realidade.
--
-- O QUE ESTA MIGRATION NAO FAZ: dizer qual e o limite de isencao. O ITCMD e
-- imposto ESTADUAL, e o limite e a aliquota mudam de estado para estado. O campo
-- nasce vazio de proposito, para ser preenchido com o numero do estado dele,
-- conferido com o contador - um numero errado aqui seria pior que numero nenhum,
-- porque passaria a tranquilizar sobre um limite que nao e o dele.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. Entrou na conta, mas nao e renda
-- --------------------------------------------------------------------------
ALTER TABLE categories
    ADD COLUMN IF NOT EXISTS counts_as_income boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN categories.counts_as_income IS
    'false quando a entrada nao e renda da familia: doacao recebida, emprestimo '
    'tomado, devolucao. O dinheiro entrou no caixa (e o fluxo e honesto), mas '
    'nao conta como renda nem na taxa de poupanca.';

-- --------------------------------------------------------------------------
-- 2. Quem doou
-- --------------------------------------------------------------------------
-- Sem CPF, de proposito. O sistema nao declara nada por ninguem, e guardar o
-- documento de terceiro so aumentaria o estrago de um vazamento. O nome basta
-- para somar por pessoa, que e para o que serve.
CREATE TABLE IF NOT EXISTS donors (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    name         text NOT NULL,
    relationship text,
    notes        text,
    is_active    boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS donors_family_idx ON donors (family_id);

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS donor_id uuid REFERENCES donors(id) ON DELETE SET NULL;

-- Para que a doacao foi dada. Nulo quando foi sem destino combinado.
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS donation_for_category_id uuid
        REFERENCES categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS transactions_donor_idx
    ON transactions (donor_id) WHERE donor_id IS NOT NULL;

COMMENT ON COLUMN transactions.donation_for_category_id IS
    'Para que a doacao foi dada. Permite abater do consumo da familia o que a '
    'doacao cobriu - a escola paga pelos avos nao e gasto da casa.';

-- --------------------------------------------------------------------------
-- 3. O limite de isencao, que e estadual
-- --------------------------------------------------------------------------
ALTER TABLE families
    ADD COLUMN IF NOT EXISTS itcmd_state char(2),
    ADD COLUMN IF NOT EXISTS itcmd_annual_exemption numeric(18, 2);

COMMENT ON COLUMN families.itcmd_annual_exemption IS
    'Limite anual de isencao do ITCMD POR DOADOR, no estado da familia. Nulo '
    'ate ser preenchido: o ITCMD e estadual, o limite muda de estado para '
    'estado e e corrigido todo ano, entao um padrao chutado aqui tranquilizaria '
    'sobre um limite que nao e o desta familia.';

-- --------------------------------------------------------------------------
-- 4. A categoria
-- --------------------------------------------------------------------------
-- ISENTO_NAO_TRIBUTAVEL porque e o que doacao recebida e na declaracao: ela nao
-- paga imposto de renda, mas e declarada em "Rendimentos Isentos e Nao
-- Tributaveis". O ITCMD, se houver, e outro imposto e outra guia - estadual, e
-- devido por quem recebe ou por quem doa conforme o estado.
WITH nova(path, name, income_nature, counts_as_income, icon) AS (VALUES
 ('receitas.doacoes',            'Doacoes recebidas', 'EVENTUAL', false, 'gift'),
 ('receitas.doacoes.familiares', 'De familiares',     'EVENTUAL', false, NULL),
 ('receitas.doacoes.outras',     'Outras doacoes',    'EVENTUAL', false, NULL)
)
INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, is_system,
                        sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       'RECEITA'::category_kind,
       path::ltree,
       income_nature::income_nature,
       'ISENTO_NAO_TRIBUTAVEL'::ir_treatment,
       'NENHUMA'::ir_deduction_type,
       false,
       true,
       counts_as_income,
       icon,
       true,
       2000 + row_number() OVER ()
FROM nova
WHERE NOT EXISTS (
    SELECT 1 FROM categories c
     WHERE c.family_id IS NULL AND c.path = nova.path::ltree
);

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND c.parent_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);

-- --------------------------------------------------------------------------
-- 5. As familias que ja existem recebem a categoria nova
-- --------------------------------------------------------------------------
-- Aqui da para copiar so o que falta, sem refazer a arvore: a categoria e nova,
-- entao ninguem tem lancamento nela e nao ha historico para preservar.
INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        expense_nature, ir_treatment, ir_deduction_type,
                        requires_note, counts_as_expense, counts_as_income,
                        icon, color, is_system, sort_order)
SELECT f.id, g.slug, g.name, g.kind, g.path, g.income_nature, g.expense_nature,
       g.ir_treatment, g.ir_deduction_type, g.requires_note, g.counts_as_expense,
       g.counts_as_income, g.icon, g.color, g.is_system, g.sort_order
  FROM families f
 CROSS JOIN (
     SELECT * FROM categories
      WHERE family_id IS NULL AND path <@ 'receitas.doacoes'::ltree
 ) g
 WHERE NOT EXISTS (
     SELECT 1 FROM categories c
      WHERE c.family_id = f.id AND c.path = g.path
 );

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NOT NULL
   AND p.family_id = c.family_id
   AND c.parent_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);
