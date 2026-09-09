-- ============================================================================
-- BBBC - Sistema de Gestao Financeira Familiar
-- Migration 0001: schema inicial
-- PostgreSQL 15+
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS ltree;      -- arvore de categorias multinivel
CREATE EXTENSION IF NOT EXISTS unaccent;   -- normalizacao de nomes de fornecedor
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy match de fornecedor

-- ---------------------------------------------------------------------------
-- Tipos enumerados
-- ---------------------------------------------------------------------------
CREATE TYPE member_role       AS ENUM ('TITULAR', 'CONJUGE', 'DEPENDENTE', 'CONTADOR');
CREATE TYPE account_type      AS ENUM ('CONTA_CORRENTE', 'POUPANCA', 'CARTAO_CREDITO',
                                       'INVESTIMENTO', 'DINHEIRO', 'PJ', 'OUTRO');
CREATE TYPE tx_direction      AS ENUM ('ENTRADA', 'SAIDA', 'TRANSFERENCIA');
CREATE TYPE tx_source         AS ENUM ('MANUAL', 'OPEN_FINANCE', 'IMPORT_OFX', 'IMPORT_CSV', 'RECORRENTE');
CREATE TYPE tx_status         AS ENUM ('PREVISTA', 'PENDENTE', 'EFETIVADA', 'CONCILIADA', 'IGNORADA');
CREATE TYPE category_kind     AS ENUM ('RECEITA', 'DESPESA', 'TRANSFERENCIA', 'INVESTIMENTO');

-- Segregacao logica pedida na taxonomia
CREATE TYPE income_nature     AS ENUM ('ATIVA_FIXA', 'ATIVA_VARIAVEL', 'PASSIVA', 'EVENTUAL');
CREATE TYPE expense_nature    AS ENUM ('ESSENCIAL', 'ESTILO_VIDA', 'METAS_PROJETOS', 'FINANCEIRO');

-- Tratamento do valor na apuracao do Imposto de Renda
CREATE TYPE ir_treatment      AS ENUM (
    'NAO_APLICAVEL',            -- despesa comum, transferencia interna
    'TRIBUTAVEL_TABELA',        -- pro-labore, alugueis, salario (tabela progressiva)
    'TRIBUTAVEL_CARNE_LEAO',    -- recebido de PF / exterior, sujeito a recolhimento mensal
    'EXCLUSIVA_FONTE',          -- CDB, LCI tributada, ganho de capital, 13o salario
    'ISENTO_NAO_TRIBUTAVEL'     -- lucros distribuidos, dividendos, poupanca, LCI/LCA
);

-- Deducoes da base de calculo (modelo completo)
CREATE TYPE ir_deduction_type AS ENUM (
    'NENHUMA',
    'SAUDE',
    'EDUCACAO',
    'PREVIDENCIA_OFICIAL',
    'PREVIDENCIA_PRIVADA_PGBL',
    'PENSAO_ALIMENTICIA',
    'LIVRO_CAIXA',
    'DEPENDENTE'
);

CREATE TYPE asset_class       AS ENUM ('RENDA_FIXA_POS', 'RENDA_FIXA_PRE', 'RENDA_FIXA_IPCA',
                                       'ACAO', 'FII', 'ETF', 'BDR', 'FUNDO', 'CRIPTO',
                                       'PREVIDENCIA', 'EXTERIOR', 'OUTRO');
CREATE TYPE connection_status AS ENUM ('CRIADA', 'AGUARDANDO_MFA', 'ATIVA', 'ERRO', 'EXPIRADA', 'REVOGADA');
CREATE TYPE goal_status       AS ENUM ('ATIVA', 'PAUSADA', 'CONCLUIDA', 'CANCELADA');
CREATE TYPE alert_severity    AS ENUM ('INFO', 'ATENCAO', 'CRITICO');
CREATE TYPE period_type       AS ENUM ('MENSAL', 'TRIMESTRAL', 'ANUAL');

-- ---------------------------------------------------------------------------
-- Nucleo: familia e membros
-- ---------------------------------------------------------------------------
CREATE TABLE families (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text        NOT NULL,
    base_currency char(3)     NOT NULL DEFAULT 'BRL',
    timezone      text        NOT NULL DEFAULT 'America/Sao_Paulo',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Felipe e Clarissa fazem login; as duas filhas existem como DEPENDENTE
-- (sem login) porque sao necessarias para as deducoes de saude/educacao no IR.
CREATE TABLE members (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id      uuid        NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    full_name      text        NOT NULL,
    nickname       text,
    role           member_role NOT NULL,
    birth_date     date,
    cpf            text,                      -- armazenar com hash/cripto em producao
    email          text,
    password_hash  text,                      -- NULL para dependentes
    is_active      boolean     NOT NULL DEFAULT true,
    -- dependente perante a Receita Federal (gera deducao anual)
    is_ir_dependent boolean    NOT NULL DEFAULT false,
    ir_dependent_of uuid       REFERENCES members(id) ON DELETE SET NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT members_email_unique UNIQUE (email),
    CONSTRAINT members_login_requires_email CHECK (password_hash IS NULL OR email IS NOT NULL)
);
CREATE INDEX members_family_idx ON members(family_id);

-- ---------------------------------------------------------------------------
-- Instituicoes, conexoes Open Finance e contas
-- ---------------------------------------------------------------------------
CREATE TABLE institutions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL,
    ispb         text,               -- identificador do SPB (bancos brasileiros)
    provider_ref text,               -- id do connector no provedor (Pluggy/Belvo)
    logo_url     text,
    UNIQUE (name)
);

CREATE TABLE bank_connections (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id          uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    owner_member_id    uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    institution_id     uuid REFERENCES institutions(id) ON DELETE SET NULL,
    provider           text NOT NULL,           -- 'pluggy' | 'belvo' | 'manual'
    provider_item_id   text,                    -- item/link id no provedor
    status             connection_status NOT NULL DEFAULT 'CRIADA',
    consent_expires_at timestamptz,             -- consentimento Open Finance (ate 12 meses)
    last_synced_at     timestamptz,
    last_error         text,
    -- credenciais NUNCA sao persistidas: o provedor guarda o vinculo.
    metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_item_id)
);
CREATE INDEX bank_connections_family_idx ON bank_connections(family_id);

CREATE TABLE accounts (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    owner_member_id   uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    institution_id    uuid REFERENCES institutions(id) ON DELETE SET NULL,
    connection_id     uuid REFERENCES bank_connections(id) ON DELETE SET NULL,
    name              text         NOT NULL,
    type              account_type NOT NULL,
    currency          char(3)      NOT NULL DEFAULT 'BRL',
    -- saldo corrente materializado (recalculado pelo servico de conciliacao)
    current_balance   numeric(18,2) NOT NULL DEFAULT 0,
    credit_limit      numeric(18,2),
    statement_close_day smallint CHECK (statement_close_day BETWEEN 1 AND 31),
    statement_due_day   smallint CHECK (statement_due_day BETWEEN 1 AND 31),
    provider_account_id text,
    -- conta compartilhada aparece na visao familiar de ambos
    is_shared         boolean      NOT NULL DEFAULT false,
    is_archived       boolean      NOT NULL DEFAULT false,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (connection_id, provider_account_id)
);
CREATE INDEX accounts_family_idx ON accounts(family_id);
CREATE INDEX accounts_owner_idx  ON accounts(owner_member_id);

-- ---------------------------------------------------------------------------
-- Taxonomia: arvore de categorias multinivel (profundidade ilimitada) + tags
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id      uuid REFERENCES families(id) ON DELETE CASCADE, -- NULL = catalogo global
    parent_id      uuid REFERENCES categories(id) ON DELETE CASCADE,
    slug           text NOT NULL,                 -- estavel, usado no path
    name           text NOT NULL,
    kind           category_kind NOT NULL,
    -- caminho materializado: 'despesas.essenciais.saude.plano_de_saude'
    path           ltree NOT NULL,
    depth          smallint NOT NULL DEFAULT 0,
    -- segregacao logica da taxonomia (aplicavel conforme o kind)
    income_nature  income_nature,
    expense_nature expense_nature,
    -- segregacao de IR herdavel pelos filhos
    ir_treatment      ir_treatment      NOT NULL DEFAULT 'NAO_APLICAVEL',
    ir_deduction_type ir_deduction_type NOT NULL DEFAULT 'NENHUMA',
    color          text,
    icon           text,
    is_system      boolean NOT NULL DEFAULT false, -- nao pode ser apagada
    is_archived    boolean NOT NULL DEFAULT false,
    sort_order     integer NOT NULL DEFAULT 0,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT categories_path_unique UNIQUE (family_id, path),
    CONSTRAINT categories_nature_matches_kind CHECK (
        (kind = 'RECEITA' AND expense_nature IS NULL)
     OR (kind = 'DESPESA' AND income_nature  IS NULL)
     OR (kind IN ('TRANSFERENCIA', 'INVESTIMENTO'))
    )
);
CREATE INDEX categories_path_gist   ON categories USING gist (path);
-- catalogo global (family_id NULL) tambem precisa de path unico
CREATE UNIQUE INDEX categories_global_path_unique ON categories(path) WHERE family_id IS NULL;
CREATE INDEX categories_parent_idx  ON categories(parent_id);
CREATE INDEX categories_family_idx  ON categories(family_id);

CREATE TABLE tags (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id  uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    name       text NOT NULL,          -- 'ViagemPraia' (sem o '#')
    color      text,
    -- tag de projeto pode ter orcamento e janela propria (ex.: #ViagemDisney)
    starts_on  date,
    ends_on    date,
    budget     numeric(18,2),
    is_archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tags_name_unique UNIQUE (family_id, name)
);

-- ---------------------------------------------------------------------------
-- Fornecedores e motor de categorizacao (aprendizado de regras)
-- ---------------------------------------------------------------------------
CREATE TABLE merchants (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid REFERENCES families(id) ON DELETE CASCADE,
    normalized_name text NOT NULL,       -- 'bambu lab', 'drogaria sao paulo'
    display_name    text NOT NULL,
    cnpj            text,
    default_category_id uuid REFERENCES categories(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT merchants_unique UNIQUE (family_id, normalized_name)
);
CREATE INDEX merchants_trgm_idx ON merchants USING gin (normalized_name gin_trgm_ops);

CREATE TABLE categorization_rules (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    -- criterios (todos opcionais, combinados com AND)
    match_type   text NOT NULL DEFAULT 'CONTEM'
                 CHECK (match_type IN ('EXATO', 'CONTEM', 'PREFIXO', 'REGEX')),
    pattern      text NOT NULL,                 -- aplicado sobre a descricao normalizada
    merchant_id  uuid REFERENCES merchants(id) ON DELETE CASCADE,
    account_id   uuid REFERENCES accounts(id)  ON DELETE CASCADE,
    min_amount   numeric(18,2),
    max_amount   numeric(18,2),
    direction    tx_direction,
    -- acao
    category_id  uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    apply_tag_id uuid REFERENCES tags(id) ON DELETE SET NULL,
    ir_deduction_member_id uuid REFERENCES members(id) ON DELETE SET NULL,
    -- aprendizado
    priority     integer NOT NULL DEFAULT 100,   -- menor = avaliado primeiro
    confidence   numeric(4,3) NOT NULL DEFAULT 0.500 CHECK (confidence BETWEEN 0 AND 1),
    hit_count    integer NOT NULL DEFAULT 0,
    last_hit_at  timestamptz,
    is_learned   boolean NOT NULL DEFAULT false, -- criada a partir de recategorizacao manual
    created_by   uuid REFERENCES members(id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX categorization_rules_family_idx ON categorization_rules(family_id, priority);

-- ---------------------------------------------------------------------------
-- Transacoes
-- ---------------------------------------------------------------------------
CREATE TABLE transactions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    account_id        uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    owner_member_id   uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    category_id       uuid REFERENCES categories(id) ON DELETE SET NULL,
    merchant_id       uuid REFERENCES merchants(id) ON DELETE SET NULL,

    booked_on         date          NOT NULL,      -- data de competencia/lancamento
    paid_on           date,                        -- data de caixa (efetivo)
    amount            numeric(18,2) NOT NULL,   -- sempre positivo; o sinal vem de direction
    direction         tx_direction  NOT NULL,
    currency          char(3)       NOT NULL DEFAULT 'BRL',

    description       text          NOT NULL,
    description_norm  text,                        -- minusculo, sem acento (match de regras)
    notes             text,

    status            tx_status     NOT NULL DEFAULT 'EFETIVADA',
    source            tx_source     NOT NULL DEFAULT 'MANUAL',
    provider_tx_id    text,                        -- idempotencia do Open Finance
    provider_payload  jsonb,

    -- parcelamento de cartao
    installment_no    smallint,
    installment_total smallint,
    installment_group uuid,

    -- pares de transferencia interna (nao entram no fluxo de caixa liquido)
    transfer_pair_id  uuid REFERENCES transactions(id) ON DELETE SET NULL,

    -- IR: quando NULL, o valor efetivo e herdado da categoria (ver v_transactions_ir)
    ir_treatment_override      ir_treatment,
    ir_deduction_type_override ir_deduction_type,
    -- a quem a despesa dedutivel pertence (ex.: consulta da filha mais nova)
    ir_deduction_member_id     uuid REFERENCES members(id) ON DELETE SET NULL,
    ir_document_number         text,               -- CNPJ/recibo do prestador
    ir_year                    smallint,           -- ano-calendario (default: year(booked_on))

    -- categorizacao automatica
    applied_rule_id   uuid REFERENCES categorization_rules(id) ON DELETE SET NULL,
    auto_confidence   numeric(4,3),
    reviewed_by       uuid REFERENCES members(id) ON DELETE SET NULL,
    reviewed_at       timestamptz,

    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT transactions_amount_positive CHECK (amount > 0),
    CONSTRAINT transactions_installments CHECK (
        (installment_no IS NULL AND installment_total IS NULL)
        OR (installment_no >= 1 AND installment_total >= 1 AND installment_no <= installment_total)
    )
);
CREATE UNIQUE INDEX transactions_provider_unique
    ON transactions(account_id, provider_tx_id) WHERE provider_tx_id IS NOT NULL;
CREATE INDEX transactions_family_date_idx ON transactions(family_id, booked_on DESC);
CREATE INDEX transactions_account_idx     ON transactions(account_id, booked_on DESC);
CREATE INDEX transactions_category_idx    ON transactions(category_id);
CREATE INDEX transactions_owner_idx       ON transactions(owner_member_id, booked_on DESC);
CREATE INDEX transactions_ir_year_idx     ON transactions(family_id, ir_year)
    WHERE ir_year IS NOT NULL;
CREATE INDEX transactions_desc_trgm_idx   ON transactions USING gin (description_norm gin_trgm_ops);

-- rateio de uma transacao em varias categorias (ex.: compra de mercado + farmacia)
CREATE TABLE transaction_splits (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id uuid NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    category_id    uuid NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    amount         numeric(18,2) NOT NULL CHECK (amount > 0),
    ir_deduction_member_id uuid REFERENCES members(id) ON DELETE SET NULL,
    notes          text
);
CREATE INDEX transaction_splits_tx_idx ON transaction_splits(transaction_id);

CREATE TABLE transaction_tags (
    transaction_id uuid NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    tag_id         uuid NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (transaction_id, tag_id)
);
CREATE INDEX transaction_tags_tag_idx ON transaction_tags(tag_id);

-- lancamentos recorrentes -> alimentam a projecao de fluxo de caixa
CREATE TABLE recurring_transactions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    account_id      uuid REFERENCES accounts(id) ON DELETE SET NULL,
    owner_member_id uuid NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    category_id     uuid REFERENCES categories(id) ON DELETE SET NULL,
    description     text NOT NULL,
    amount          numeric(18,2) NOT NULL CHECK (amount > 0),
    direction       tx_direction NOT NULL,
    rrule           text NOT NULL,        -- iCal RRULE, ex.: FREQ=MONTHLY;BYMONTHDAY=5
    next_run_on     date NOT NULL,
    ends_on         date,
    auto_post       boolean NOT NULL DEFAULT false,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Previsoes: tetos por categoria e metas de longo prazo
-- ---------------------------------------------------------------------------
CREATE TABLE budget_caps (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    category_id  uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    -- NULL = teto familiar; preenchido = teto individual daquele membro
    member_id    uuid REFERENCES members(id) ON DELETE CASCADE,
    period       period_type   NOT NULL DEFAULT 'MENSAL',
    amount       numeric(18,2) NOT NULL CHECK (amount > 0),
    -- inclui subcategorias na apuracao do teto
    includes_descendants boolean NOT NULL DEFAULT true,
    starts_on    date NOT NULL DEFAULT date_trunc('month', now())::date,
    ends_on      date,
    alert_at_pct numeric(4,3) NOT NULL DEFAULT 0.800 CHECK (alert_at_pct BETWEEN 0 AND 2),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT budget_caps_unique UNIQUE (family_id, category_id, member_id, period, starts_on)
);

CREATE TABLE goals (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    name              text NOT NULL,                   -- 'Viagem Disney 2028'
    description       text,
    target_amount     numeric(18,2) NOT NULL CHECK (target_amount > 0),
    target_date       date NOT NULL,
    current_amount    numeric(18,2) NOT NULL DEFAULT 0,
    monthly_contribution numeric(18,2) NOT NULL DEFAULT 0,
    -- taxa nominal anual esperada do fundo da meta (ex.: 0.1100 = 11% a.a.)
    expected_annual_rate numeric(6,4) NOT NULL DEFAULT 0,
    -- corrige o alvo pela inflacao ate a data-alvo
    inflation_indexed boolean NOT NULL DEFAULT false,
    linked_account_id uuid REFERENCES accounts(id) ON DELETE SET NULL,
    linked_tag_id     uuid REFERENCES tags(id) ON DELETE SET NULL,
    status            goal_status NOT NULL DEFAULT 'ATIVA',
    priority          smallint NOT NULL DEFAULT 1,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE goal_contributions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id        uuid NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    transaction_id uuid REFERENCES transactions(id) ON DELETE SET NULL,
    member_id      uuid REFERENCES members(id) ON DELETE SET NULL,
    contributed_on date NOT NULL,
    amount         numeric(18,2) NOT NULL CHECK (amount <> 0),
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX goal_contributions_goal_idx ON goal_contributions(goal_id, contributed_on);

-- ---------------------------------------------------------------------------
-- Investimentos
-- ---------------------------------------------------------------------------
CREATE TABLE assets (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id     uuid REFERENCES families(id) ON DELETE CASCADE, -- NULL = catalogo global
    symbol        text,                     -- PETR4, HGLG11, ...
    name          text NOT NULL,
    asset_class   asset_class NOT NULL,
    issuer        text,                     -- emissor do CDB / gestora do fundo
    -- indexador: 'CDI', 'IPCA', 'PRE', 'SELIC'
    benchmark_code text,
    -- percentual do indexador (1.1200 = 112% do CDI) ou taxa pre (0.1250 = 12,5% a.a.)
    contracted_rate numeric(8,4),
    maturity_date date,
    -- isencao de IR do papel (LCI, LCA, debenture incentivada, poupanca)
    is_ir_exempt  boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT assets_symbol_unique UNIQUE (family_id, symbol)
);

CREATE TABLE positions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id     uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    account_id    uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    asset_id      uuid NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    owner_member_id uuid NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    quantity      numeric(24,8) NOT NULL DEFAULT 0,
    average_price numeric(18,6) NOT NULL DEFAULT 0,
    invested_amount numeric(18,2) NOT NULL DEFAULT 0,
    market_value  numeric(18,2) NOT NULL DEFAULT 0,
    opened_on     date,
    closed_on     date,
    provider_position_id text,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT positions_unique UNIQUE (account_id, asset_id, owner_member_id)
);
CREATE INDEX positions_family_idx ON positions(family_id);

-- serie historica para a curva de evolucao patrimonial
CREATE TABLE position_snapshots (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id   uuid NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    snapshot_on   date NOT NULL,
    quantity      numeric(24,8) NOT NULL,
    market_value  numeric(18,2) NOT NULL,
    invested_amount numeric(18,2) NOT NULL,
    CONSTRAINT position_snapshots_unique UNIQUE (position_id, snapshot_on)
);

CREATE TABLE investment_transactions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id   uuid NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    transaction_id uuid REFERENCES transactions(id) ON DELETE SET NULL,
    kind          text NOT NULL CHECK (kind IN ('APORTE','RESGATE','COMPRA','VENDA',
                                                'PROVENTO','JCP','AMORTIZACAO','TAXA','IR_RETIDO')),
    traded_on     date NOT NULL,
    quantity      numeric(24,8),
    unit_price    numeric(18,6),
    gross_amount  numeric(18,2) NOT NULL,
    fees          numeric(18,2) NOT NULL DEFAULT 0,
    withheld_tax  numeric(18,2) NOT NULL DEFAULT 0,   -- IR retido na fonte
    ir_treatment  ir_treatment NOT NULL DEFAULT 'EXCLUSIVA_FONTE',
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX investment_transactions_pos_idx ON investment_transactions(position_id, traded_on);

-- serie de indicadores (CDI, IPCA, SELIC, IBOV) para o comparativo
CREATE TABLE benchmark_series (
    code        text NOT NULL,              -- 'CDI', 'IPCA', 'SELIC', 'IBOV'
    reference_on date NOT NULL,
    -- variacao do periodo em fracao (0.0089 = 0,89% no mes)
    period_rate numeric(12,8) NOT NULL,
    -- indice acumulado base 100 na primeira data carregada
    index_value numeric(18,8),
    source      text,
    PRIMARY KEY (code, reference_on)
);

-- ---------------------------------------------------------------------------
-- Imposto de Renda: parametros versionados por ano-calendario
-- ---------------------------------------------------------------------------
CREATE TABLE tax_years (
    year            smallint PRIMARY KEY,
    -- 'PROVISORIO' enquanto a IN da Receita do ano nao foi publicada
    status          text NOT NULL DEFAULT 'PROVISORIO'
                    CHECK (status IN ('PROVISORIO', 'VIGENTE', 'ENCERRADO')),
    source_reference text,                  -- lei/IN que embasa os numeros
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- tabela progressiva (mensal e anual). Nada de aliquota em codigo.
CREATE TABLE tax_brackets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    year        smallint NOT NULL REFERENCES tax_years(year) ON DELETE CASCADE,
    scope       text NOT NULL CHECK (scope IN ('MENSAL', 'ANUAL')),
    min_base    numeric(18,2) NOT NULL,
    max_base    numeric(18,2),              -- NULL = ultima faixa
    rate        numeric(6,4)  NOT NULL CHECK (rate BETWEEN 0 AND 1),
    deduction   numeric(18,2) NOT NULL DEFAULT 0,  -- parcela a deduzir
    valid_from  date,                       -- faixas que mudam no meio do ano
    CONSTRAINT tax_brackets_unique UNIQUE (year, scope, min_base, valid_from)
);

-- limites e valores parametrizados: deducao por dependente, teto de educacao,
-- desconto simplificado, faixa de isencao de venda de acoes etc.
CREATE TABLE tax_parameters (
    year        smallint NOT NULL REFERENCES tax_years(year) ON DELETE CASCADE,
    key         text     NOT NULL,
    value       numeric(18,4) NOT NULL,
    unit        text     NOT NULL DEFAULT 'BRL',  -- 'BRL' | 'PCT' | 'QTD'
    description text,
    PRIMARY KEY (year, key)
);

-- informes de rendimento (fonte pagadora) usados para bater a apuracao
CREATE TABLE ir_income_statements (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id     uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    member_id     uuid NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    year          smallint NOT NULL REFERENCES tax_years(year) ON DELETE RESTRICT,
    payer_name    text NOT NULL,           -- 'Checkmotor'
    payer_cnpj    text,
    taxable_income        numeric(18,2) NOT NULL DEFAULT 0,
    exempt_income         numeric(18,2) NOT NULL DEFAULT 0,
    exclusive_taxed_income numeric(18,2) NOT NULL DEFAULT 0,
    withheld_tax          numeric(18,2) NOT NULL DEFAULT 0,
    official_pension      numeric(18,2) NOT NULL DEFAULT 0,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ir_income_statements_unique UNIQUE (family_id, member_id, year, payer_cnpj, payer_name)
);

-- resultado da apuracao (cache auditavel do motor de calculo)
CREATE TABLE ir_assessments (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id      uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    member_id      uuid NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    year           smallint NOT NULL REFERENCES tax_years(year) ON DELETE RESTRICT,
    model          text NOT NULL CHECK (model IN ('COMPLETO', 'SIMPLIFICADO')),
    taxable_income numeric(18,2) NOT NULL,
    total_deductions numeric(18,2) NOT NULL,
    calculation_base numeric(18,2) NOT NULL,
    tax_due        numeric(18,2) NOT NULL,
    withheld_tax   numeric(18,2) NOT NULL,
    balance        numeric(18,2) NOT NULL,   -- >0 a pagar, <0 a restituir
    effective_rate numeric(6,4)  NOT NULL,
    breakdown      jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ir_assessments_unique UNIQUE (family_id, member_id, year, model)
);

-- ---------------------------------------------------------------------------
-- Alertas e observabilidade das sincronizacoes
-- ---------------------------------------------------------------------------
CREATE TABLE alerts (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id   uuid NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    member_id   uuid REFERENCES members(id) ON DELETE CASCADE,  -- NULL = familia toda
    kind        text NOT NULL,   -- 'TETO_ESTOURADO','META_ATRASADA','CONSENTIMENTO_EXPIRANDO',...
    severity    alert_severity NOT NULL DEFAULT 'INFO',
    title       text NOT NULL,
    body        text,
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX alerts_family_idx ON alerts(family_id, created_at DESC);

CREATE TABLE sync_logs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id uuid REFERENCES bank_connections(id) ON DELETE CASCADE,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    status        text NOT NULL DEFAULT 'EXECUTANDO'
                  CHECK (status IN ('EXECUTANDO','SUCESSO','ERRO')),
    accounts_synced     integer NOT NULL DEFAULT 0,
    transactions_created integer NOT NULL DEFAULT 0,
    transactions_updated integer NOT NULL DEFAULT 0,
    error_message text
);

CREATE TABLE webhook_events (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider      text NOT NULL,
    event_id      text,
    event_type    text NOT NULL,
    payload       jsonb NOT NULL,
    signature_ok  boolean NOT NULL DEFAULT false,
    processed_at  timestamptz,
    received_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT webhook_events_unique UNIQUE (provider, event_id)
);

-- ---------------------------------------------------------------------------
-- Views de apoio
-- ---------------------------------------------------------------------------

-- Resolve o tratamento de IR efetivo: override da transacao > categoria.
CREATE VIEW v_transactions_ir AS
SELECT t.id,
       t.family_id,
       t.owner_member_id,
       t.booked_on,
       COALESCE(t.ir_year, EXTRACT(YEAR FROM t.booked_on)::smallint) AS ir_year,
       t.amount,
       t.direction,
       c.path AS category_path,
       COALESCE(t.ir_treatment_override, c.ir_treatment, 'NAO_APLICAVEL')          AS ir_treatment,
       COALESCE(t.ir_deduction_type_override, c.ir_deduction_type, 'NENHUMA')      AS ir_deduction_type,
       t.ir_deduction_member_id
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.status IN ('EFETIVADA', 'CONCILIADA')
  AND t.direction <> 'TRANSFERENCIA';

-- Fluxo de caixa mensal por categoria (base do dashboard e do Sankey).
CREATE VIEW v_monthly_cashflow AS
SELECT t.family_id,
       t.owner_member_id,
       date_trunc('month', t.booked_on)::date AS month,
       t.direction,
       c.id   AS category_id,
       c.path AS category_path,
       c.kind AS category_kind,
       SUM(t.amount) AS total
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
WHERE t.status IN ('EFETIVADA', 'CONCILIADA')
  AND t.direction <> 'TRANSFERENCIA'
GROUP BY 1,2,3,4,5,6,7;

-- ---------------------------------------------------------------------------
-- Triggers utilitarios
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['families','members','accounts','bank_connections','categories',
                               'categorization_rules','transactions','budget_caps','goals','positions']
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_set_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', tbl, tbl);
    END LOOP;
END $$;

-- Mantem path/depth coerentes quando uma categoria e criada ou movida.
CREATE OR REPLACE FUNCTION categories_sync_path() RETURNS trigger AS $$
DECLARE parent_path ltree;
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        SELECT path INTO parent_path FROM categories WHERE id = NEW.parent_id;
        IF parent_path IS NULL THEN
            RAISE EXCEPTION 'Categoria pai % nao encontrada', NEW.parent_id;
        END IF;
        NEW.path  := parent_path || NEW.slug::ltree;
    ELSIF NEW.path IS NULL THEN
        -- raiz sem path explicito
        NEW.path := NEW.slug::ltree;
    END IF;
    -- clonagem em lote informa o path pronto e amarra o parent_id depois
    NEW.depth := nlevel(NEW.path) - 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER categories_sync_path_trg
    BEFORE INSERT OR UPDATE OF parent_id, slug ON categories
    FOR EACH ROW EXECUTE FUNCTION categories_sync_path();

-- Reposiciona a subarvore quando o pai muda.
CREATE OR REPLACE FUNCTION categories_move_subtree() RETURNS trigger AS $$
BEGIN
    IF NEW.path <> OLD.path AND pg_trigger_depth() = 1 THEN
        UPDATE categories
           SET path  = NEW.path || subpath(path, nlevel(OLD.path)),
               depth = nlevel(NEW.path || subpath(path, nlevel(OLD.path))) - 1
         WHERE path <@ OLD.path AND id <> NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- 'AFTER UPDATE OF path' nao serve aqui: o path e reescrito pelo trigger BEFORE,
-- e nao pela clausula SET do UPDATE. A condicao WHEN cobre os dois casos.
CREATE TRIGGER categories_move_subtree_trg
    AFTER UPDATE ON categories
    FOR EACH ROW
    WHEN (NEW.path IS DISTINCT FROM OLD.path)
    EXECUTE FUNCTION categories_move_subtree();
