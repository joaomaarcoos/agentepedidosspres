-- Protocolo interno para diferenciar pedidos criados pela IA dos pedidos reais do Clic Vendas.
ALTER TABLE pedidos_revisao
  ADD COLUMN IF NOT EXISTS protocolo text,
  ADD COLUMN IF NOT EXISTS origem text NOT NULL DEFAULT 'ia_whatsapp',
  ADD COLUMN IF NOT EXISTS clic_num_ped text;

UPDATE pedidos_revisao
SET protocolo = 'SP-' || to_char(created_at AT TIME ZONE 'America/Sao_Paulo', 'YYMMDD') || '-' || upper(substr(id::text, 1, 6))
WHERE protocolo IS NULL OR btrim(protocolo) = '';

ALTER TABLE pedidos_revisao
  ALTER COLUMN protocolo SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pedidos_revisao_protocolo
  ON pedidos_revisao(protocolo);

CREATE INDEX IF NOT EXISTS idx_pedidos_revisao_telefone_status_updated
  ON pedidos_revisao(cliente_telefone, status, updated_at DESC);
