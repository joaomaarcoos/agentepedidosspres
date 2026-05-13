-- Migration: create system_settings table
-- Run this in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tsnvhhrifxcnuszzaxfk/sql

CREATE TABLE IF NOT EXISTS system_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL DEFAULT 'true',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO system_settings (key, value) VALUES
  ('disparo_recorrencia_enabled', 'true'),
  ('disparo_ativacao_enabled', 'true')
ON CONFLICT (key) DO NOTHING;
