-- Auditoria neutra de requisicoes enviadas para integracoes externas.
-- Mantem compatibilidade copiando o historico legado de clic_request_logs.

CREATE TABLE IF NOT EXISTS public.requisition_logs (
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

CREATE INDEX IF NOT EXISTS requisition_logs_created_idx
  ON public.requisition_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS requisition_logs_status_created_idx
  ON public.requisition_logs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS requisition_logs_order_idx
  ON public.requisition_logs(order_id);

CREATE INDEX IF NOT EXISTS requisition_logs_rep_created_idx
  ON public.requisition_logs(cod_rep, created_at DESC);

INSERT INTO public.requisition_logs (
  id,
  source,
  operation,
  endpoint,
  method,
  status,
  http_status,
  order_id,
  protocol,
  cod_rep,
  representative_document,
  customer_code,
  customer_document,
  request_payload,
  response_payload,
  error_message,
  created_at,
  sent_at,
  responded_at,
  duration_ms
)
SELECT
  id,
  source,
  operation,
  endpoint,
  method,
  status,
  http_status,
  order_id,
  protocol,
  cod_rep,
  representative_document,
  customer_code,
  customer_document,
  request_payload,
  response_payload,
  error_message,
  created_at,
  sent_at,
  responded_at,
  duration_ms
FROM public.clic_request_logs
ON CONFLICT (id) DO NOTHING;
