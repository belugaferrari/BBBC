-- ============================================================================
-- Migration 0006: patrimonio, participacoes, controle de extratos,
--                 vencimentos, notificacoes e pontos de cartao
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1 e 2. Patrimonio nao financeiro: imoveis, terrenos e participacoes
--
-- Uma tabela so para os dois, porque sao a mesma coisa do ponto de vista do
-- sistema e da Receita: bem que voce possui, com valor de aquisicao e valor de
-- hoje. O app mostra em duas telas; o dado e um.
-- ---------------------------------------------------------------------------
CREATE TYPE holding_kind AS ENUM (
    'IMOVEL', 'TERRENO', 'VEICULO', 'PARTICIPACAO', 'OUTRO'
);

CREATE TABLE holdings (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    owner_member_id   uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    kind              holding_kind NOT NULL,
    name              text NOT NULL,
    description       text,

    acquired_on       date,
    acquisition_value numeric(18,2),
    -- valor de hoje, atualizado por holding_valuations
    current_value     numeric(18,2) NOT NULL DEFAULT 0,

    -- A Receita declara bem pelo CUSTO DE AQUISICAO, nao pelo valor de mercado.
    -- Guardar os dois separados evita a confusao mais cara do IR sobre bens.
    ir_declared_value numeric(18,2),

    -- participacao societaria
    company_cnpj      text,
    ownership_percentage numeric(7,4) CHECK (
        ownership_percentage IS NULL
        OR (ownership_percentage > 0 AND ownership_percentage <= 100)
    ),

    -- imovel
    registration      text,          -- matricula
    address           text,

    is_active         boolean NOT NULL DEFAULT true,
    sold_on           date,
    sale_value        numeric(18,2),

    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT holdings_participacao_tem_percentual CHECK (
        kind <> 'PARTICIPACAO' OR ownership_percentage IS NOT NULL
    ),
    CONSTRAINT holdings_venda_coerente CHECK (
        (sold_on IS NULL AND sale_value IS NULL) OR sold_on IS NOT NULL
    )
);
CREATE INDEX holdings_family_idx ON holdings(family_id, kind) WHERE is_active;

-- Historico de reavaliacao: e o que permite ver o patrimonio evoluir, em vez
-- de so ter o numero de hoje.
CREATE TABLE holding_valuations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    holding_id  uuid NOT NULL REFERENCES holdings(id) ON DELETE CASCADE,
    valued_on   date NOT NULL,
    value       numeric(18,2) NOT NULL,
    source      text,           -- 'avaliacao', 'IPTU', 'oferta de mercado'...
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT holding_valuations_unique UNIQUE (holding_id, valued_on)
);

-- ---------------------------------------------------------------------------
-- 3. Recebimento de extrato mensal
--
-- Nao ha tabela nova de controle: o extrato recebido JA e o registro em
-- statement_imports. O que faltava era dizer de quais contas se espera extrato.
-- Guardar o mesmo fato duas vezes seria criar a chance de eles discordarem.
-- ---------------------------------------------------------------------------
ALTER TABLE accounts
    ADD COLUMN IF NOT EXISTS expects_statement boolean NOT NULL DEFAULT true,
    -- dia em que o extrato costuma ficar disponivel
    ADD COLUMN IF NOT EXISTS statement_expected_day smallint
        CHECK (statement_expected_day IS NULL
               OR statement_expected_day BETWEEN 1 AND 31);

-- ---------------------------------------------------------------------------
-- 4. Aviso de vencimento
-- ---------------------------------------------------------------------------
ALTER TABLE recurring_transactions
    ADD COLUMN IF NOT EXISTS remind_days_before smallint NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS is_bill boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN recurring_transactions.is_bill IS
    'true para conta com vencimento (luz, escola, fatura): gera aviso antes.';

-- Evita repetir o mesmo aviso todo dia ate a conta vencer.
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS dedupe_key text,
    ADD COLUMN IF NOT EXISTS due_on date;

CREATE UNIQUE INDEX alerts_dedupe_unique
    ON alerts(family_id, dedupe_key) WHERE dedupe_key IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 5. Notificacoes: celular, computador e e-mail
-- ---------------------------------------------------------------------------
CREATE TYPE notification_channel AS ENUM ('PUSH', 'EMAIL');

CREATE TABLE notification_targets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id   uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    member_id   uuid NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    channel     notification_channel NOT NULL,
    -- token do Expo (push) ou endereco de e-mail
    address     text NOT NULL,
    device_name text,
    platform    text,           -- ios | android | web
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    CONSTRAINT notification_targets_unique UNIQUE (member_id, channel, address)
);

-- Uma linha por (alerta, destino): e o que impede o mesmo aviso de chegar duas
-- vezes no mesmo aparelho quando o envio e reexecutado.
CREATE TABLE notification_deliveries (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id    uuid NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    target_id   uuid NOT NULL REFERENCES notification_targets(id) ON DELETE CASCADE,
    status      text NOT NULL DEFAULT 'PENDENTE'
                CHECK (status IN ('PENDENTE', 'ENVIADO', 'ERRO', 'DESCARTADO')),
    attempts    smallint NOT NULL DEFAULT 0,
    error       text,
    sent_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT notification_deliveries_unique UNIQUE (alert_id, target_id)
);
CREATE INDEX notification_deliveries_pendentes_idx
    ON notification_deliveries(status) WHERE status = 'PENDENTE';

-- ---------------------------------------------------------------------------
-- 6. Pontos de cartao de credito
-- ---------------------------------------------------------------------------
CREATE TABLE card_programs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id     uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    account_id    uuid REFERENCES accounts(id) ON DELETE SET NULL,
    name          text NOT NULL,          -- Livelo, Smiles, TudoAzul...
    card_name     text,                   -- 'Itau Personnalite Visa Infinite'

    -- pontos por unidade gasta. `currency_basis` diz por unidade de que:
    -- cartao brasileiro costuma pontuar por DOLAR gasto, e nao por real.
    points_per_currency numeric(10,4) NOT NULL DEFAULT 0,
    currency_basis      char(3) NOT NULL DEFAULT 'USD',

    balance       numeric(14,2) NOT NULL DEFAULT 0,
    -- valor de referencia do ponto, para estimar quanto o saldo vale
    point_value_brl numeric(10,4),

    expires_next_on     date,
    expires_next_points numeric(14,2),

    is_active     boolean NOT NULL DEFAULT true,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX card_programs_family_idx ON card_programs(family_id) WHERE is_active;

CREATE TABLE point_movements (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id    uuid NOT NULL REFERENCES card_programs(id) ON DELETE CASCADE,
    transaction_id uuid REFERENCES transactions(id) ON DELETE SET NULL,
    moved_on      date NOT NULL,
    kind          text NOT NULL CHECK (kind IN (
                      'ACUMULO', 'RESGATE', 'EXPIRACAO', 'TRANSFERENCIA', 'AJUSTE', 'BONUS')),
    -- positivo entra, negativo sai
    points        numeric(14,2) NOT NULL,
    description   text,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX point_movements_program_idx ON point_movements(program_id, moved_on DESC);

-- ---------------------------------------------------------------------------
-- Triggers de updated_at para as tabelas novas
-- ---------------------------------------------------------------------------
DO $$
DECLARE tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['holdings', 'card_programs']
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_set_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', tbl, tbl);
    END LOOP;
END $$;
