-- Tipo de venda escolhido pela secretaria antes do envio ao Clic.

ALTER TABLE public.secretary_orders
  ADD COLUMN IF NOT EXISTS sale_type_code text NOT NULL DEFAULT '90100';

CREATE INDEX IF NOT EXISTS secretary_orders_sale_type_idx
  ON public.secretary_orders(sale_type_code, created_at DESC);
