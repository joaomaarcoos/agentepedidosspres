-- Tabela de pedidos aguardando revisão do representante
CREATE TABLE IF NOT EXISTS pedidos_revisao (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
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
