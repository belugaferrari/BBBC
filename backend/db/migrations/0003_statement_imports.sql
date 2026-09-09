-- ============================================================================
-- Migration 0003: importacao de extratos (OFX, CSV, PDF)
-- ============================================================================

-- PDF entra como origem propria: a extracao e por heuristica e a interface
-- precisa saber que aquele lancamento merece mais conferencia.
ALTER TYPE tx_source ADD VALUE IF NOT EXISTS 'IMPORT_PDF';

CREATE TABLE statement_imports (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    account_id       uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    uploaded_by      uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,

    filename         text NOT NULL,
    file_format      text NOT NULL CHECK (file_format IN ('OFX', 'CSV', 'PDF')),
    file_hash        text NOT NULL,          -- sha256 do arquivo: reenvio e detectado
    file_size        integer NOT NULL,

    -- CRIADO = pre-visualizado, ainda nao gravou nada
    status           text NOT NULL DEFAULT 'CRIADO'
                     CHECK (status IN ('CRIADO', 'CONFIRMADO', 'DESCARTADO', 'ERRO')),

    period_start     date,
    period_end       date,
    rows_detected    integer NOT NULL DEFAULT 0,
    rows_duplicated  integer NOT NULL DEFAULT 0,
    rows_imported    integer NOT NULL DEFAULT 0,

    -- lancamentos extraidos, guardados para a tela de conferencia
    preview          jsonb NOT NULL DEFAULT '[]'::jsonb,
    warnings         jsonb NOT NULL DEFAULT '[]'::jsonb,
    error_message    text,

    created_at       timestamptz NOT NULL DEFAULT now(),
    confirmed_at     timestamptz
);
CREATE INDEX statement_imports_family_idx ON statement_imports(family_id, created_at DESC);
-- Reenvio do mesmo arquivo e RECONHECIDO, nao proibido: o lote entra, a
-- pre-visualizacao marca tudo como duplicado e a confirmacao grava zero linha.
-- Bloquear aqui transformaria um reenvio inofensivo em erro de banco. Quem
-- garante a nao duplicacao e transactions_import_fingerprint_unique.
CREATE INDEX statement_imports_file_idx ON statement_imports(account_id, file_hash);

ALTER TABLE transactions
    ADD COLUMN import_id uuid REFERENCES statement_imports(id) ON DELETE SET NULL,
    -- impressao digital do lancamento importado: data + valor + descricao
    -- normalizada. E o que impede a mesma linha de entrar duas vezes quando os
    -- extratos de dois meses se sobrepoem.
    ADD COLUMN import_fingerprint text;

CREATE UNIQUE INDEX transactions_import_fingerprint_unique
    ON transactions(account_id, import_fingerprint)
    WHERE import_fingerprint IS NOT NULL;
CREATE INDEX transactions_import_idx ON transactions(import_id) WHERE import_id IS NOT NULL;
