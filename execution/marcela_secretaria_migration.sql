-- Marcela Secretaria: conversas, pedidos e rastreabilidade no ClicVendas.

CREATE TABLE IF NOT EXISTS public.secretary_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_key text NOT NULL UNIQUE,
  instance_name text NOT NULL,
  representative_phone text NOT NULL,
  cod_rep integer NOT NULL,
  state_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.secretary_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES public.secretary_conversations(id) ON DELETE CASCADE,
  external_message_id text,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'event')),
  content text NOT NULL DEFAULT '',
  payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS secretary_messages_external_uidx
  ON public.secretary_messages(conversation_id, external_message_id)
  WHERE external_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.secretary_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocol text NOT NULL UNIQUE,
  conversation_id uuid REFERENCES public.secretary_conversations(id) ON DELETE SET NULL,
  instance_name text NOT NULL,
  cod_rep integer NOT NULL,
  representative_phone text NOT NULL,
  customer_code text NOT NULL,
  customer_document text,
  customer_name text NOT NULL,
  price_table_code text,
  items_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  observations text NOT NULL DEFAULT '',
  total numeric(15,2) NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'awaiting_confirmation', 'submitting', 'submitted', 'synced', 'failed', 'cancelled')),
  idempotency_key text NOT NULL UNIQUE,
  clic_order_number text,
  clic_external_id text,
  clic_status text,
  submit_payload jsonb,
  submit_response jsonb,
  error_message text,
  confirmed_at timestamptz,
  submitted_at timestamptz,
  synced_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS secretary_orders_rep_created_idx
  ON public.secretary_orders(cod_rep, created_at DESC);
CREATE INDEX IF NOT EXISTS secretary_orders_status_created_idx
  ON public.secretary_orders(status, created_at DESC);
CREATE INDEX IF NOT EXISTS secretary_orders_clic_number_idx
  ON public.secretary_orders(clic_order_number);

ALTER TABLE public.rep_order_base
  ADD COLUMN IF NOT EXISTS origin_agent text,
  ADD COLUMN IF NOT EXISTS origin_order_id uuid,
  ADD COLUMN IF NOT EXISTS origin_instance text,
  ADD COLUMN IF NOT EXISTS origin_cod_rep integer,
  ADD COLUMN IF NOT EXISTS origin_protocol text,
  ADD COLUMN IF NOT EXISTS external_id text,
  ADD COLUMN IF NOT EXISTS observation text;

CREATE INDEX IF NOT EXISTS rep_order_base_origin_agent_idx
  ON public.rep_order_base(origin_agent, dat_emi DESC);
CREATE INDEX IF NOT EXISTS rep_order_base_origin_protocol_idx
  ON public.rep_order_base(origin_protocol);

