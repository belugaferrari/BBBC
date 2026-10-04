-- ============================================================================
-- Migration 0016: reembolso - o dinheiro que volta
--
-- "Quando eu pago algo e os amigos passam a parte deles."
--
-- Ele paga R$ 300 do jantar e tres amigos devolvem R$ 75 cada. Sem um lugar
-- para isso, o mes conta os R$ 300 como gasto da casa E os R$ 225 como RENDA -
-- erra duas vezes, e nas duas para o lado de parecer melhor do que foi: mais
-- renda e, depois, uma taxa de poupanca que nao existe.
--
-- E a mesma familia de problema da doacao, com uma diferenca que importa: a
-- doacao e dinheiro de outra pessoa que CHEGA; o reembolso e dinheiro dele que
-- VOLTA. Por isso nao pode cair no mesmo balde - no relatorio de doacoes, o
-- reembolso do jantar apareceria como doacao de alguem, e o limite de isencao do
-- ITCMD passaria a contar dinheiro que nunca foi doado.
--
-- Duas pecas:
--
--   1. `receitas.reembolsos`, com `counts_as_income = false`: entrou na conta,
--      nao e renda.
--   2. `transactions.reembolso_de_id`, que liga o dinheiro que voltou AO GASTO
--      que ele devolve. Sem a ligacao daria para somar os reembolsos do mes,
--      mas nao para saber se eles ja passaram do que foi gasto - e reembolso
--      maior que a conta nao e reembolso, e outra coisa.
--
-- O QUE ESTA MIGRATION NAO MUDA: o gasto continua aparecendo inteiro na
-- categoria dele. O jantar de R$ 300 fica como R$ 300 em Restaurantes, com o
-- quanto voltou escrito ao lado. Quem desconta o reembolso e o CONSUMO DA
-- FAMILIA, no Resumo - a mesma regra que ja vale para a doacao. Misturar os
-- dois criterios (descontar aqui, nao descontar ali) daria dois numeros para a
-- mesma pergunta, que e pior que um numero bruto bem explicado.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. A categoria
-- --------------------------------------------------------------------------
INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, is_system,
                        sort_order)
SELECT NULL, 'reembolsos', 'Reembolsos', 'RECEITA'::category_kind,
       'receitas.reembolsos'::ltree, 'EVENTUAL'::income_nature,
       -- Reembolso nao e rendimento: e dinheiro proprio voltando. Nao entra em
       -- lugar nenhum da declaracao, nem como isento.
       'NAO_APLICAVEL'::ir_treatment, 'NENHUMA'::ir_deduction_type,
       false, true, false, 'refresh', true, 2100
WHERE NOT EXISTS (
    SELECT 1 FROM categories
     WHERE family_id IS NULL AND path = 'receitas.reembolsos'::ltree
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
      WHERE family_id IS NULL AND path = 'receitas.reembolsos'::ltree
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

-- --------------------------------------------------------------------------
-- 2. A ligacao com o gasto que voltou
-- --------------------------------------------------------------------------
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS reembolso_de_id uuid
        REFERENCES transactions(id) ON DELETE SET NULL;

COMMENT ON COLUMN transactions.reembolso_de_id IS
    'Para uma ENTRADA de reembolso: qual gasto ela devolve. Permite dizer '
    'quanto daquele gasto ja voltou, e impedir que um reembolso maior que a '
    'conta abata mais do que foi gasto.';

-- A consulta e sempre "quanto voltou DESTE gasto", entao o indice e pelo alvo.
CREATE INDEX IF NOT EXISTS transactions_reembolso_de_idx
    ON transactions (reembolso_de_id)
    WHERE reembolso_de_id IS NOT NULL;
