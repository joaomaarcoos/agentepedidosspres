-- Migration para modulo ClicVendas
-- Executa no Supabase SQL Editor

-- 1. Criar tabela de logs de sincronizacao (se nao existir)
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

-- 2. Criar base de pedidos antes de adicionar colunas faltantes
CREATE TABLE IF NOT EXISTS rep_order_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_rep INTEGER,
    cod_cli INTEGER,
    customer_document TEXT,
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

-- 3. Adicionar colunas faltantes em instalacoes existentes
ALTER TABLE rep_order_base
    ADD COLUMN IF NOT EXISTS customer_document TEXT,
    ADD COLUMN IF NOT EXISTS customer_name TEXT,
    ADD COLUMN IF NOT EXISTS rep_name TEXT,
    ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'clic_vendas',
    ADD COLUMN IF NOT EXISTS erp_synced_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS items_json JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS has_items BOOLEAN DEFAULT FALSE;

-- 4. Indices para performance
CREATE INDEX IF NOT EXISTS idx_clic_sync_logs_created_at ON clic_sync_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clic_sync_logs_status ON clic_sync_logs(status);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_dat_emi ON rep_order_base(dat_emi DESC);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_cod_cli ON rep_order_base(cod_cli);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_cod_rep ON rep_order_base(cod_rep);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_customer_document ON rep_order_base(customer_document);
CREATE INDEX IF NOT EXISTS idx_rep_order_base_source ON rep_order_base(source);
