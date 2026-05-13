-- Migration: create disparo_logs table
-- Run this in Supabase SQL Editor:
-- https://supabase.com/dashboard/project/tsnvhhrifxcnuszzaxfk/sql

CREATE TABLE IF NOT EXISTS disparo_logs (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  flow          TEXT        NOT NULL CHECK (flow IN ('recorrencia', 'ativacao')),
  triggered_by  TEXT        NOT NULL DEFAULT 'manual',
  dry_run       BOOLEAN     NOT NULL DEFAULT false,
  processed     INTEGER     NOT NULL DEFAULT 0,
  dispatched    INTEGER     NOT NULL DEFAULT 0,
  skipped       INTEGER     NOT NULL DEFAULT 0,
  errors_count  INTEGER     NOT NULL DEFAULT 0,
  errors_json   JSONB       NOT NULL DEFAULT '[]',
  status        TEXT        NOT NULL DEFAULT 'success'
                            CHECK (status IN ('success', 'partial', 'error', 'dry_run')),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  duration_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_disparo_logs_flow       ON disparo_logs (flow);
CREATE INDEX IF NOT EXISTS idx_disparo_logs_started_at ON disparo_logs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_disparo_logs_status     ON disparo_logs (status);
