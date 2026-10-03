-- ============================================================================
-- Migration 0012: as entradas dele, e o cartao que vem sem detalhe
--
-- Tres assuntos, e os tres sao sobre a mesma coisa: dinheiro aparecendo (ou
-- desaparecendo) do lugar errado.
--
--   1. TRANSFERENCIA QUE ENTRA NAO E RENDA. Ja existia o espelho do lado da
--      saida: amortizacao e pagamento de fatura saem da conta e nao contam como
--      gasto (`counts_as_expense = false`, migration 0005 e 0009). Faltava o
--      lado da entrada - e o furo aparece na primeira fatura de cartao
--      importada: o OFX do cartao traz a LINHA DO PAGAMENTO dela como credito,
--      e aquele credito estava entrando como RENDA DA FAMILIA. Testado: R$
--      4.320,15 de fatura paga viravam R$ 4.320,15 de renda, e a taxa de
--      poupanca subia para 89%. Pior: nao havia como consertar pela tela, nem
--      classificando a linha como "Pagamento de fatura", porque a coluna nao
--      existia para aquele lado.
--
--   2. AS ENTRADAS QUE ELE TEM. "Precisamos fazer categorias de entrada. Alem
--      de doacao, podemos por Salario Clarissa; Salario Felipe; Dividendos
--      Check; Dividendos LDM". Entram como filhas das categorias que o motor de
--      IR ja entende, e nao como arvore nova solta: assim o tratamento fiscal
--      vem herdado e certo, em vez de ser redigitado.
--
--   3. O CARTAO SEM DETALHE. No extrato de conta corrente dele o cartao aparece
--      como UMA linha, o total pago, sem as compras. Classificada como
--      "Pagamento de fatura", essa linha nao conta como gasto - o que esta certo
--      quando as compras foram importadas da fatura, e esta ERRADO quando nao
--      foram: ai o gasto do cartao simplesmente desaparece do mes, e o mes
--      parece mais barato do que foi. "Cartao (sem detalhe)" e o lugar honesto
--      para quando ele decidir nao detalhar: conta como gasto, num valor so, e
--      diz no proprio nome que o detalhe nao esta ali.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. Transferencia que entra nao e renda
-- --------------------------------------------------------------------------
UPDATE categories
   SET counts_as_income = false
 WHERE path <@ 'transferencias'::ltree;

COMMENT ON COLUMN categories.counts_as_income IS
    'false quando a entrada nao e renda da familia: doacao recebida, '
    'transferencia entre contas proprias, credito de pagamento de fatura, '
    'emprestimo tomado, devolucao. O dinheiro entrou no caixa (e o fluxo '
    'continua honesto), mas nao conta como renda nem na taxa de poupanca. '
    'Quem distingue DOACAO das outras entradas que nao sao renda e o caminho '
    'da categoria (receitas.doacoes), e nao esta coluna - as duas nao sao a '
    'mesma coisa e somadas no mesmo balde o Resumo chamaria de doacao o '
    'pagamento da propria fatura.';

-- --------------------------------------------------------------------------
-- 2. As entradas dele
-- --------------------------------------------------------------------------
-- Por que sob as categorias que ja existem, em vez de uma arvore nova:
--
--   * salario e pro-labore sao TRIBUTAVEL_TABELA, e e a mae que ja diz isso;
--   * distribuicao de lucros e dividendo sao ISENTO_NAO_TRIBUTAVEL hoje, e
--     tambem ja esta dito na mae.
--
-- Ele escreveu "Dividendos". Numa LTDA o nome tecnico e distribuicao de lucros,
-- e o sistema tem as duas arvores - mas para o imposto de renda as duas caem no
-- mesmo lugar (isento, declarado em "Rendimentos Isentos e Nao Tributaveis"),
-- entao a escolha do nome nao muda numero nenhum. Fica a palavra dele.
WITH nova(path, name, income_nature, ir_treatment, ordem) AS (VALUES
 ('receitas.ativa_fixa.salario.felipe',   'Felipe',   'ATIVA_FIXA', 'TRIBUTAVEL_TABELA',     10),
 ('receitas.ativa_fixa.salario.clarissa', 'Clarissa', 'ATIVA_FIXA', 'TRIBUTAVEL_TABELA',     20),
 ('receitas.passiva.dividendos.check',    'Check',    'PASSIVA',    'ISENTO_NAO_TRIBUTAVEL', 10),
 ('receitas.passiva.dividendos.ldm',      'LDM',      'PASSIVA',    'ISENTO_NAO_TRIBUTAVEL', 20)
)
INSERT INTO categories (family_id, slug, name, kind, path, income_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, is_system,
                        sort_order)
SELECT NULL,
       subpath(path::ltree, nlevel(path::ltree) - 1)::text,
       name,
       'RECEITA'::category_kind,
       path::ltree,
       income_nature::income_nature,
       ir_treatment::ir_treatment,
       'NENHUMA'::ir_deduction_type,
       false,
       true,
       true,
       true,
       ordem
FROM nova
WHERE NOT EXISTS (
    SELECT 1 FROM categories c
     WHERE c.family_id IS NULL AND c.path = nova.path::ltree
);

-- --------------------------------------------------------------------------
-- 3. O cartao sem detalhe
-- --------------------------------------------------------------------------
-- ESSENCIAL de proposito: o que foi comprado no cartao e, na media, consumo da
-- casa. Classificar como estilo de vida faria o mes parecer mais discricionario
-- do que e; e, sem o detalhe, nao da para saber.
INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, is_system,
                        sort_order)
SELECT NULL, 'cartao_sem_detalhe', 'Cartão (sem detalhe)', 'DESPESA'::category_kind,
       'despesas.cartao_sem_detalhe'::ltree, 'ESSENCIAL'::expense_nature,
       'NAO_APLICAVEL'::ir_treatment, 'NENHUMA'::ir_deduction_type,
       false, true, true, 'card', true, 8900
WHERE NOT EXISTS (
    SELECT 1 FROM categories
     WHERE family_id IS NULL AND path = 'despesas.cartao_sem_detalhe'::ltree
);

-- --------------------------------------------------------------------------
-- 4. Amarrar os pais e levar para as familias que ja existem
-- --------------------------------------------------------------------------
UPDATE categories c
   SET parent_id = p.id
  FROM categories p
 WHERE c.family_id IS NULL
   AND p.family_id IS NULL
   AND c.parent_id IS NULL
   AND nlevel(c.path) > 1
   AND p.path = subpath(c.path, 0, nlevel(c.path) - 1);

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
        AND (path <@ 'receitas.ativa_fixa.salario'::ltree
             OR path <@ 'receitas.passiva.dividendos'::ltree
             OR path = 'despesas.cartao_sem_detalhe'::ltree)
        AND nlevel(path) > 2
 ) g
 WHERE NOT EXISTS (
     SELECT 1 FROM categories c
      WHERE c.family_id = f.id AND c.path = g.path
 );

-- A de nivel 2 (o proprio "Cartao (sem detalhe)") entra separada: o filtro
-- acima pede nlevel > 2 para nao recopiar "Salario" e "Dividendos", que as
-- familias ja tem.
INSERT INTO categories (family_id, slug, name, kind, path, expense_nature,
                        ir_treatment, ir_deduction_type, requires_note,
                        counts_as_expense, counts_as_income, icon, is_system,
                        sort_order)
SELECT f.id, g.slug, g.name, g.kind, g.path, g.expense_nature, g.ir_treatment,
       g.ir_deduction_type, g.requires_note, g.counts_as_expense,
       g.counts_as_income, g.icon, g.is_system, g.sort_order
  FROM families f
 CROSS JOIN (
     SELECT * FROM categories
      WHERE family_id IS NULL AND path = 'despesas.cartao_sem_detalhe'::ltree
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
