export interface SyncLog {
  id: string;
  triggered_at: string;
  triggered_by: "manual" | "schedule" | "auto";
  status: "running" | "success" | "partial" | "error";
  rep_document?: string;
  date_from?: string;
  total_fetched: number;
  total_upserted: number;
  total_errors: number;
  duration_ms?: number;
  error_message?: string;
  result_summary_json?: {
    total_clientes?: number;
    status_breakdown?: Record<string, number>;
    date_from?: string;
    dias?: number;
  };
  created_at: string;
}

export interface Pedido {
  id?: string;
  cod_rep?: number;
  cod_cli?: number | string;
  customer_name?: string;
  rep_name?: string;
  num_ped?: number;
  dat_emi?: string;
  sit_ped?: string;
  order_total_value?: number;
  items_json?: PedidoItem[];
  has_items?: boolean;
  source?: string;
  erp_synced_at?: string;
}

export interface PedidoItem {
  codPro?: string;
  desPro?: string;
  qtdPed?: number;
  preUni?: number;
  uniMed?: string;
  vlrTotal?: number;
}

export interface ApiStatus {
  ok: boolean;
  service?: string;
  version?: string;
  mode?: string;
}

export interface ConexaoStatus {
  service: string;
  checked_at: string;
  configured: boolean;
  api_online: boolean;
  instance_found: boolean;
  instance_name?: string | null;
  connection_state?: string | null;
  latency_ms: number;
  error_message?: string | null;
  api_url?: string | null;
  env: Record<string, boolean>;
}

export interface EvolutionInstance {
  instanceName: string;
  instanceId?: string;
  status: string;
  profilePictureUrl?: string | null;
  phoneNumber?: string | null;
}

export interface EvolutionInstancesResponse {
  instances: EvolutionInstance[];
  total: number;
  api_online: boolean;
  api_url: string | null;
  checked_at: string;
  env: Record<string, boolean>;
}

export interface CreateInstanceResult {
  instanceName: string;
  instanceId: string;
  status: string;
  qrcode?: { code: string; base64: string } | null;
}

export interface QrCodeResult {
  instanceName: string;
  code: string;
  base64: string;
}

export interface InstanceActionResult {
  instanceName: string;
  success: boolean;
  message: string;
}

export interface Cliente {
  external_id: string;
  cod_cli?: number | null;
  nome?: string | null;
  razao_social?: string | null;
  fantasia?: string | null;
  documento?: string | null;
  email?: string | null;
  telefone?: string | null;
  cidade?: string | null;
  uf?: string | null;
  ativo?: boolean;
  source?: string;
  synced_at?: string;
  raw_json?: Record<string, unknown>;
  total_pedidos?: number;
  valor_total_acumulado?: number;
  ultimo_pedido_em?: string | null;
  ultimo_pedido_valor?: number | null;
  ultimo_pedido_numero?: number | null;
  ultimo_pedido_status?: string | null;
  primeiro_pedido_em?: string | null;
  dias_entre_pedidos_media?: number | null;
  proximo_pedido_estimado_em?: string | null;
  historico_situacoes_json?: Record<string, number> | null;
  top_produtos_json?: Array<Record<string, unknown>> | null;
}

export interface ClientesListResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  active: number;
  inactive: number;
  clientes: Cliente[];
}

export interface ClientesSyncResponse {
  status: "success" | "error";
  message: string;
  total_fetched: number;
  total_upserted: number;
  duration_ms: number;
}

export interface RecorrenciaItem {
  codPro: string;
  desPro: string;
  qtdPed: number;
  vlrTotal: number;
}

export interface RecorrenciaOrderDetail {
  numero: number | null;
  data: string;
  valor_total: number;
  situacao: string | null;
  itens: RecorrenciaItem[];
}

export interface RecorrenciaTopItem {
  codPro: string;
  desPro: string;
  total_qtd: number;
  aparicoes: number;
}

export type RecorrenciaStatus =
  | "candidate"
  | "ai_approved"
  | "ai_rejected"
  | "dispatched"
  | "responded"
  | "converted"
  | "opted_out";

export interface RecorrenciaTarget {
  id: string;
  cpf_cnpj: string;
  customer_name: string | null;
  customer_phone: string | null;
  cod_rep: number | null;
  recurrence_interval_days: number | null;
  recurrence_tier: "media" | "alta" | "semanal_forte" | null;
  last_order_date: string | null;
  predicted_next_order_date: string | null;
  days_until_predicted: number | null;
  orders_count_30d: number | null;
  last_3_orders_json: RecorrenciaOrderDetail[] | null;
  top_items_json: RecorrenciaTopItem[] | null;
  status: RecorrenciaStatus;
  ai_validated: boolean;
  ai_decision: string | null;
  ai_reasoning: string | null;
  dispatched_at: string | null;
  cooldown_until: string | null;
  last_contact_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecorrenciaOverview {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  stats: {
    candidate: number;
    ai_approved: number;
    ai_rejected: number;
    dispatched: number;
    responded: number;
    converted: number;
    opted_out: number;
  };
  targets: RecorrenciaTarget[];
}
