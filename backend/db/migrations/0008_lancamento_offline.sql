-- ============================================================================
-- Migration 0008: lancamento criado no celular, sem o servidor por perto
--
-- Com o PC desligado o aplicativo guarda o lancamento numa fila e sobe depois.
-- Subir uma fila nao e operacao confiavel: a conexao cai no meio, o aplicativo
-- e fechado, o usuario tenta de novo. Sem identidade propria, cada retentativa
-- criaria um gasto novo - e duplicata em base financeira so aparece no fim do
-- mes, quando o total nao bate e ninguem lembra por que.
--
-- client_key e gerada no celular, uma por lancamento, antes mesmo de existir
-- conexao. O servidor usa a chave para reconhecer o que ja gravou e devolver o
-- mesmo lancamento em vez de criar outro.
-- ============================================================================

ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS client_key text;

COMMENT ON COLUMN transactions.client_key IS
    'Identidade gerada pelo aplicativo antes de haver conexao. Permite reenviar '
    'a fila sem duplicar. NULL em tudo que nasceu no servidor.';

-- Por familia, e nao global: duas familias nunca compartilham a fila, e o
-- indice parcial deixa de fora todo o historico, que nao tem chave.
CREATE UNIQUE INDEX IF NOT EXISTS transactions_client_key_unique
    ON transactions (family_id, client_key)
 WHERE client_key IS NOT NULL;
