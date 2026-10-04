-- ============================================================================
-- Migration 0013: extrato em planilha (.xlsx)
--
-- "Tenho aqui planilhas (xlsx) com o extrato do cartao, mas o sistema
-- aparentemente nao le esse tipo de arquivo (so csv)."
--
-- Duas colunas precisam saber do formato novo: a que registra o lote importado
-- (com CHECK, que recusaria 'XLSX') e a que diz de onde cada lancamento veio.
-- A segunda nao e burocracia: e por ela que se descobre, meses depois, que
-- aquele lancamento estranho veio de uma planilha e nao do OFX do banco - e
-- planilha e o formato em que o proprio usuario pode ter mexido antes.
-- ============================================================================

ALTER TABLE statement_imports DROP CONSTRAINT IF EXISTS statement_imports_file_format_check;
ALTER TABLE statement_imports
    ADD CONSTRAINT statement_imports_file_format_check
    CHECK (file_format IN ('OFX', 'CSV', 'PDF', 'XLSX'));

-- Em PostgreSQL um valor novo de enum so pode ser USADO depois que a transacao
-- que o criou termina - criar aqui e usar no mesmo lote daria erro. Como as
-- migrations rodam uma por transacao e nenhuma linha e escrita com este valor
-- agora, esta certo.
ALTER TYPE tx_source ADD VALUE IF NOT EXISTS 'IMPORT_XLSX';
