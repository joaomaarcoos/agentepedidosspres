-- Tabela de pedidos aguardando revisão do representante
CREATE TABLE IF NOT EXISTS pedidos_revisao (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  protocolo text NOT NULL DEFAULT ('SP-' || to_char(now() AT TIME ZONE 'America/Sao_Paulo', 'YYMMDD') || '-' || upper(substr(gen_random_uuid()::text, 1, 6))),
  origem text NOT NULL DEFAULT 'ia_whatsapp',
  clic_num_ped text,
  conversation_id uuid REFERENCES ai_conversations(id) ON DELETE SET NULL,
  cliente_nome text,
  cliente_telefone text NOT NULL,
  itens_json jsonb NOT NULL DEFAULT '[]',
  observacoes text NOT NULL DEFAULT '',
  mensagem_cliente text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'pendente'
    CHECK (status IN ('pendente', 'em_revisao', 'pedido_feito', 'cancelado')),
  revisado_em timestamptz,
  revisado_por text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pedidos_revisao_status_created
  ON pedidos_revisao(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pedidos_revisao_telefone
  ON pedidos_revisao(cliente_telefone);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pedidos_revisao_protocolo
  ON pedidos_revisao(protocolo);
