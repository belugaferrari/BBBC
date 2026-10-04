-- ============================================================================
-- Migration 0015: "Assinaturas > Outras"
--
-- "Preciso de uma assinatura mensal generica tambem. assinatura>>outras"
--
-- As assinaturas nasceram com tres filhas (streaming, livros, IA e softwares).
-- Assinatura que nao e nenhuma das tres - academia, nuvem, jornal, o aplicativo
-- que ninguem lembra de cancelar - nao tinha onde cair, e ia parar na categoria
-- mae. Gasto na mae some do detalhe: a tela mostra "Assinaturas" com um numero
-- que nao se abre em nada.
-- ============================================================================

INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, is_system, sort_order)
SELECT NULL, 'outras', 'Outras assinaturas', 'DESPESA'::category_kind,
       'despesas.gastos_mensais.assinaturas.outras'::ltree,
       'ESTILO_VIDA'::expense_nature, 'NAO_APLICAVEL'::ir_treatment,
       -- As irmas vao de 1008 a 1010; "Outras" fecha a lista, como manda o
       -- proprio nome: e o balde do que nao e nenhuma das outras.
       'NENHUMA'::ir_deduction_type, false, true, true, true, 1011
WHERE NOT EXISTS (
    SELECT 1 FROM categories
     WHERE family_id IS NULL
       AND path = 'despesas.gastos_mensais.assinaturas.outras'::ltree
);

INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, color,
                        is_system, sort_order)
SELECT f.id, g.slug, g.name, g.kind, g.path, g.expense_nature, g.ir_treatment,
       g.ir_deduction_type, g.requires_note, g.counts_as_expense,
       g.counts_as_income, g.icon, g.color, g.is_system, g.sort_order
  FROM families f
 CROSS JOIN (
     SELECT * FROM categories
      WHERE family_id IS NULL
        AND path = 'despesas.gastos_mensais.assinaturas.outras'::ltree
 ) g
 WHERE NOT EXISTS (
     SELECT 1 FROM categories c
      WHERE c.family_id = f.id AND c.path = g.path
 );

UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.parent_id IS NULL
   AND nlevel(c.path) > 1
   AND p.family_id IS NOT DISTINCT FROM c.family_id
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);
