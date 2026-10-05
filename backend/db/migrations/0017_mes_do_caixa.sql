-- ============================================================================
-- Migration 0017: o mes em que o dinheiro sai da conta
--
-- "O extrato do cartao vem com a data da efetivacao da compra, nao com a data
-- do pagamento do cartao. (...) o valor so e contabilizado como gasto no mes em
-- que ele efetivamente saiu da conta."
--
-- Sao duas datas, e ate agora o sistema so usava uma:
--
--   * `booked_on` e QUANDO ACONTECEU - o dia da compra, o que esta no extrato,
--     o que ele lembra. Continua sendo o que aparece na lista.
--   * `paid_on` e QUANDO O DINHEIRO SAIU. Em conta corrente, o mesmo dia. No
--     cartao, o vencimento da fatura que cobra aquela compra.
--
-- A partir daqui o MES de tudo que fala de dinheiro - Resumo, categorias,
-- metas, evolucao - e o do `paid_on`. Assim o mes do sistema fecha com o
-- extrato bancario, que e o documento contra o qual ele confere.
--
-- A coluna `paid_on` ja existia, nula e sem uso. Ganha regra, valor para toda
-- linha que ja existe, e NOT NULL - uma data de caixa opcional seria um
-- COALESCE em cada consulta do sistema, e um dia alguem esqueceria um.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. A regra, em SQL, para a carga das linhas que ja existem
--
-- A mesma regra vive em app/services/caixa.py, que e quem decide no momento da
-- gravacao. Duas implementacoes da mesma conta e um risco real de divergirem,
-- entao ha um teste que compara as duas numa grade de datas e configuracoes
-- (tests/test_mes_do_caixa.py). Preferi isso a carregar em Python: a carga tem
-- de acontecer DENTRO da migration, na mesma transacao, senao existe um
-- instante em que o sistema esta no ar com metade das linhas sem data de caixa.
-- --------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION bbbc_fatura_que_cobra(
    compra date, fechamento smallint, vencimento smallint
) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    WITH dias AS (
        SELECT COALESCE(fechamento, 31) AS fecha,
               COALESCE(vencimento, 10) AS vence
    ),
    -- 1. qual fatura pega a compra: a que fecha depois dela
    fecha_em AS (
        SELECT CASE
                 WHEN EXTRACT(DAY FROM compra)
                      > LEAST(dias.fecha, EXTRACT(DAY FROM (date_trunc('month', compra)
                                                   + INTERVAL '1 month - 1 day'))::int)
                 THEN date_trunc('month', compra) + INTERVAL '1 month'
                 ELSE date_trunc('month', compra)
               END AS mes,
               dias.fecha, dias.vence
          FROM dias
    ),
    -- 2. quando essa fatura vence: vencimento menor que o fechamento e do mes
    --    seguinte (fecha dia 25, vence dia 5)
    vence_em AS (
        SELECT CASE WHEN vence <= fecha THEN mes + INTERVAL '1 month' ELSE mes END AS mes,
               vence
          FROM fecha_em
    )
    SELECT (mes + (LEAST(
                vence,
                EXTRACT(DAY FROM (mes + INTERVAL '1 month - 1 day'))::int
            ) - 1) * INTERVAL '1 day')::date
      FROM vence_em;
$$;

COMMENT ON FUNCTION bbbc_fatura_que_cobra(date, smallint, smallint) IS
    'O vencimento da fatura que cobra uma compra feita nesta data. Gemea de '
    'app/services/caixa.py:fatura_que_cobra, conferida por teste.';

-- --------------------------------------------------------------------------
-- 2. A coluna
-- --------------------------------------------------------------------------
UPDATE transactions t
   SET paid_on = CASE
       WHEN a.type = 'CARTAO_CREDITO' AND t.direction = 'SAIDA'
           -- so a COMPRA espera a fatura. O credito dentro do cartao (o
           -- pagamento da propria fatura) acontece no dia em que acontece.
           THEN bbbc_fatura_que_cobra(
                    t.booked_on, a.statement_close_day, a.statement_due_day)
       ELSE t.booked_on
   END
  FROM accounts a
 WHERE a.id = t.account_id
   AND t.paid_on IS DISTINCT FROM CASE
       WHEN a.type = 'CARTAO_CREDITO' AND t.direction = 'SAIDA'
           THEN bbbc_fatura_que_cobra(
                    t.booked_on, a.statement_close_day, a.statement_due_day)
       ELSE t.booked_on
   END;

-- Lancamento sem conta nao existe (a coluna e NOT NULL), mas o banco nao sabe
-- disso aqui - e NOT NULL com uma linha de fora derrubaria a migration inteira.
UPDATE transactions SET paid_on = booked_on WHERE paid_on IS NULL;

ALTER TABLE transactions ALTER COLUMN paid_on SET NOT NULL;

COMMENT ON COLUMN transactions.paid_on IS
    'O dia em que o dinheiro sai da conta. Em conta corrente e igual a '
    'booked_on; no cartao e o vencimento da fatura que cobra a compra. E a '
    'data que define o MES de tudo que fala de dinheiro.';

-- O Resumo pergunta "o mes inteiro desta familia" o tempo todo.
CREATE INDEX IF NOT EXISTS transactions_paid_on_idx
    ON transactions (family_id, paid_on);
