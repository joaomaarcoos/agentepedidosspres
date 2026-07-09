-- Migracao legada. Use execution/requisition_logs_migration.sql para novos ambientes.

CREATE TABLE IF NOT EXISTS public.clic_request_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL DEFAULT 'secretary',
  operation text NOT NULL DEFAULT 'create_order',
  endpoint text NOT NULL,
  method text NOT NULL DEFAULT 'POST',
  status text NOT NULL CHECK (status IN ('pending', 'success', 'error')),
  http_status integer,
  order_id uuid,
  protocol text,
  cod_rep integer,
  representative_document text,
  customer_code text,
  customer_document text,
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  response_payload jsonb,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  responded_at timestamptz,
  duration_ms integer
);

CREATE INDEX IF NOT EXISTS clic_request_logs_created_idx
  ON public.clic_request_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS clic_request_logs_status_created_idx
  ON public.clic_request_logs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS clic_request_logs_order_idx
  ON public.clic_request_logs(order_id);

CREATE INDEX IF NOT EXISTS clic_request_logs_rep_created_idx
  ON public.clic_request_logs(cod_rep, created_at DESC);
