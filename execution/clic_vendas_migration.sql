-- Migration para módulo ClicVendas
-- Executa no Supabase SQL Editor

-- 1. Criar tabela de logs de sincronização (se não existir)
CREATE TABLE IF NOT EXISTS clic_sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_by TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'running',
    rep_document TEXT,
    date_from TEXT,
    total_fetched INTEGER DEFAULT 0,
    total_upserted INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error_message TEXT,
    result_summary_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Adicionar colunas faltantes em rep_order_base (se existir a tabela)
DO $$
BEGIN
    -- Adiciona customer_name se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'customer_name') THEN
        ALTER TABLE rep_order_base ADD COLUMN customer_name TEXT;
    END IF;

    -- Adiciona rep_name se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'rep_name') THEN
        ALTER TABLE rep_order_base ADD COLUMN rep_name TEXT;
    END IF;

    -- Adiciona source se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'source') THEN
        ALTER TABLE rep_order_base ADD COLUMN source TEXT DEFAULT 'clic_vendas';
    END IF;

    -- Adiciona erp_synced_at se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'erp_synced_at') THEN
        ALTER TABLE rep_order_base ADD COLUMN erp_synced_at TIMESTAMPTZ;
    END IF;

    -- Adiciona items_json se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'items_json') THEN
        ALTER TABLE rep_order_base ADD COLUMN items_json JSONB DEFAULT '[]'::jsonb;
    END IF;

    -- Adiciona has_items se não existir
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'rep_order_base' AND column_name = 'has_items') THEN
        ALTER TABLE rep_order_base ADD COLUMN has_items BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- 3. Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_clic_sync_logs_created_at ON clic_sync_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clic_sync_logs_status ON clic_sync_logs(status);

-- 4. Se a tabela rep_order_base não existir, criar ela completa
CREATE TABLE IF NOT EXISTS rep_order_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_rep INTEGER,
    cod_cli INTEGER,
    customer_name TEXT,
    rep_name TEXT,
    num_ped TEXT,
    dat_emi TEXT,
    sit_ped TEXT,
    order_total_value NUMERIC(15,2) DEFAULT 0,
    items_json JSONB DEFAULT '[]'::jsonb,
    has_items BOOLEAN DEFAULT FALSE,
    source TEXT DEFAULT 'clic_vendas',
    erp_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cod_rep, num_ped)
);

-- 5. Índices para rep_order_base
CREATE INDEX IF NOT EXISTS idx_rep_order_base_dat_emi ON rep_order_base(dat_emi DESC);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_cod_cli ON rep_order_base(cod_cli);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_source ON rep_order_base(source);
