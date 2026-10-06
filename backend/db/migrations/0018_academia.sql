-- ============================================================================
-- Migration 0018: academia, dentro dos gastos mensais
--
-- "Nos gastos, alguns comecam com ACM - e minha academia. Crie uma categoria
-- mensais>academia e quando o sistema ler ACM, sugira o gasto dentro dessa
-- categoria."
--
-- A categoria vem aqui; a regra que reconhece "ACM" vive em
-- app/services/default_rules.py, que e recarregado a cada partida do sistema.
-- Sao coisas separadas de proposito: categoria e estrutura, e sobrevive a
-- qualquer mudanca de catalogo de fornecedor; regra e palpite, e e refeita do
-- zero toda vez que o sistema sobe.
-- ============================================================================

INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, is_system,
                        sort_order)
SELECT NULL, 'academia', 'Academia', 'DESPESA'::category_kind,
       'despesas.gastos_mensais.academia'::ltree,
       -- Estilo de vida, e nao essencial: ela mora entre as contas do mes pela
       -- regularidade (vence todo mes, como a internet), mas quem olha "onde da
       -- para cortar" precisa ver a academia de um lado e a luz do outro. E a
       -- mesma leitura que as assinaturas ja tinham.
       'ESTILO_VIDA'::expense_nature,
       'NAO_APLICAVEL'::ir_treatment, 'NENHUMA'::ir_deduction_type,
       false, true, true, NULL, true, 1012
WHERE NOT EXISTS (
    SELECT 1 FROM categories
     WHERE family_id IS NULL AND path = 'despesas.gastos_mensais.academia'::ltree
);

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
        AND path = 'despesas.gastos_mensais.academia'::ltree
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
