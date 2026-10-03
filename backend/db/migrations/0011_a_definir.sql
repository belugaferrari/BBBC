-- ============================================================================
-- Migration 0011: "A definir" - a categoria para o que ainda nao se sabe
--
-- "Nem sempre pelo nome dos gastos vou saber o que e." Pedido dele, e o pedido
-- conserta um erro que ja existia.
--
-- Antes, lancamento que nenhuma regra reconhecia entrava com categoria NULA. A
-- analise por categoria (`spend_by_category`) ja tratava esse caso: ela usa LEFT
-- JOIN e junta tudo num balde chamado "Sem categoria". Mas esse balde e um
-- ROTULO CALCULADO, nao uma categoria - e a diferenca aparece em tres lugares:
--
--   * a tela de Categorias (`category_overview`) nasce da arvore de categorias.
--     Gasto sem categoria nao tem linha la, entao ele simplesmente nao aparece -
--     e o total daquela tela fica menor que o "Gastou" do Resumo, que soma
--     lancamento direto. Numero que nao fecha e sem explicacao e pior que numero
--     ausente;
--   * rotulo calculado nao abre: nao da para entrar nele, ver os lancamentos,
--     comparar com o mes passado nem por meta;
--   * e nao da para escolher "Sem categoria" ao lancar a mao, porque nao existe
--     nada para escolher - era justamente o que faltava: "nem sempre pelo nome
--     dos gastos vou saber o que e".
--
-- Com uma categoria de verdade, o pendente aparece na lista com nome e total,
-- da para abrir, da para filtrar, e some de lá no dia em que ele disser o que
-- era.
--
-- POR QUE A DE RECEITA CONTA COMO RENDA. `receitas.a_definir` entra com
-- `counts_as_income = true`, e isso e decisao, nao descuido: entrada que ninguem
-- classificou ainda e dinheiro que esta na conta. Marcar como "nao e renda"
-- esconderia receita de verdade e, pior, ela seria somada ao balde de doacoes no
-- Resumo, que e onde moram as entradas que nao sao renda - um rotulo errado no
-- lugar de um rotulo faltando.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. No catalogo global
-- --------------------------------------------------------------------------
-- `sort_order` alto de proposito: a categoria do que falta decidir fica no fim
-- da lista, nao competindo com as que tem significado.
WITH nova(path, name, kind, income_nature, expense_nature, icon) AS (VALUES
 ('despesas.a_definir', 'A definir', 'DESPESA', NULL,       'ESTILO_VIDA', 'help'),
 ('receitas.a_definir', 'A definir', 'RECEITA', 'EVENTUAL', NULL,          'help')
)
INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        expense_nature, ir_treatment, ir_deduction_type,
                        requires_note, counts_as_expense, counts_as_income,
                        icon, is_system, sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       kind::category_kind,
       path::ltree,
       income_nature::income_nature,
       expense_nature::expense_nature,
       'NAO_APLICAVEL'::ir_treatment,
       'NENHUMA'::ir_deduction_type,
       -- Nao exige comentario: o lancamento cai aqui justamente quando ainda nao
       -- se sabe o que foi. Exigir explicacao seria travar a importacao pedindo
       -- a informacao que nao existe ainda.
       false,
       true,
       true,
       icon,
       true,
       9000
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
-- 2. Nas familias que ja existem
-- --------------------------------------------------------------------------
-- A categoria e nova, ninguem tem lancamento nela, nao ha historico a preservar:
-- copiar o que falta basta.
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
      WHERE family_id IS NULL
        AND path IN ('despesas.a_definir'::ltree, 'receitas.a_definir'::ltree)
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

-- --------------------------------------------------------------------------
-- 3. O que ja estava solto vai para la
-- --------------------------------------------------------------------------
-- Lancamento sem categoria que ja existe no banco e o mesmo caso: ele esta fora
-- da soma por categoria agora. Mandar para "A definir" o torna visivel, que e o
-- unico jeito de ele ser resolvido algum dia.
--
-- TRANSFERENCIA fica de fora: ela nao e gasto nem receita, e pedir uma categoria
-- para "pagamento de fatura" seria pedir uma decisao que nao existe.
UPDATE transactions t
   SET category_id = c.id
  FROM categories c
 WHERE t.category_id IS NULL
   AND c.family_id = t.family_id
   AND c.path = CASE t.direction
                    WHEN 'SAIDA'   THEN 'despesas.a_definir'::ltree
                    WHEN 'ENTRADA' THEN 'receitas.a_definir'::ltree
                END;
