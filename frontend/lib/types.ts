export interface Produto {
  id: string;
  filial: string;
  cod_produto: string;
  nome: string;
  derivacao: string;
  preco_base: number | null;
  preco_inst_299: number | null;
  preco_tabela_201?: number | null;
  preco_tabela_201p?: number | null;
  preco_tabela_202?: number | null;
  preco_tabela_205?: number | null;
  preco_tabela_206?: number | null;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProdutosListResponse {
  ok: boolean;
  produtos: Produto[];
  total: number;
}

export interface PromptFile {
  slug: string;
  filename: string;
  label: string;
  description: string;
  content: string;
  lines: number;
  core: boolean;
  updatedAt: string;
}

export type PedidoRevisaoStatus = "pendente" | "em_revisao" | "pedido_feito" | "cancelado";

export interface PedidoRevisaoItem {
  cod_produto?: string;
  nome?: string;
  produto?: string;
  tipo?: string;
  formato?: string;
  tamanho?: string;
  derivacao?: string;
  variacao?: string;
  volume?: string;
  quantidade?: string | number;
  unidade?: string;
  preco_unitario?: number;
  subtotal?: number;
}

export interface PedidoRevisao {
  id: string;
  protocolo?: string | null;
  origem?: string | null;
  clic_num_ped?: string | null;
  conversation_id?: string | null;
  cliente_nome?: string | null;
  cliente_telefone: string;
  itens_json: PedidoRevisaoItem[];
  observacoes: string;
  mensagem_cliente: string;
  status: PedidoRevisaoStatus;
  revisado_em?: string | null;
  revisado_por?: string | null;
  created_at: string;
  updated_at: string;
  conversation_messages?: { role: string; content: string; created_at: string }[];
}

export interface PedidoRevisaoListResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  stats: Record<PedidoRevisaoStatus, number>;
  pedidos: PedidoRevisao[];
}

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
    rep_document?: string | null;
    pages?: number;
    total_geral?: number | null;
    secretary_orders_reconciled?: number;
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

export interface PrevisaoProduto {
  codPro: string;
  desPro: string;
  total_qtd: number;
  total_valor: number;
  pedidos: number;
  growth_pct: number | null;
}

export interface PrevisaoPeriodo {
  period: number;
  label: string;
  orders_count: number;
  items_count: number;
  total_qtd: number;
  total_valor: number;
  top_products: PrevisaoProduto[];
}

export interface PrevisaoMes {
  month: number;
  label: string;
  orders_count: number;
  items_count: number;
  total_qtd: number;
  total_valor: number;
  top_products: PrevisaoProduto[];
}

export interface PrevisaoOverview {
  year: number;
  period_count: number;
  available_years: number[];
  latest_period: number;
  seasonal_reference_month?: number;
  seasonal_reference_label?: string;
  summary: {
    orders_count: number;
    items_count: number;
    total_qtd: number;
    total_valor: number;
    products_count: number;
    secretary_orders_count: number;
    secretary_total_value: number;
  };
  periods: PrevisaoPeriodo[];
  months?: PrevisaoMes[];
  seasonal_products?: PrevisaoProduto[];
  forecast_products: PrevisaoProduto[];
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
  agent_type?: AgentType;
  agent_enabled?: boolean;
}

export type AgentType = "sales" | "secretary";

export type SecretaryOrderStatus =
  | "draft"
  | "awaiting_confirmation"
  | "submitting"
  | "submitted"
  | "synced"
  | "failed"
  | "cancelled";

export interface SecretaryOrderItem {
  cod_produto?: string | number | null;
  nome?: string | null;
  derivacao?: string | null;
  quantidade?: number | null;
  unidade?: string | null;
  preco_unitario?: number | null;
  subtotal?: number | null;
}

export interface SecretaryOrder {
  id: string;
  protocol: string;
  instance_name: string;
  cod_rep: number;
  representative_phone?: string | null;
  customer_code?: string | number | null;
  customer_name?: string | null;
  items_json: SecretaryOrderItem[];
  total: number;
  status: SecretaryOrderStatus;
  clic_order_number?: string | null;
  clic_status?: string | null;
  error_message?: string | null;
  confirmed_at?: string | null;
  submitted_at?: string | null;
  synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SecretaryMetrics {
  orders_started: number;
  orders_confirmed: number;
  orders_sent: number;
  orders_synced: number;
  orders_failed: number;
  total_value: number;
  average_ticket: number;
  customers: number;
  representatives: number;
  instances: number;
  status_breakdown: Record<string, number>;
  products: Array<{
    code?: string | number | null;
    name?: string | null;
    quantity: number;
    value: number;
  }>;
  daily: Array<{ date: string; started: number; sent: number; value: number }>;
  representative_totals: Array<{
    cod_rep: number;
    name: string;
    orders: number;
    value: number;
  }>;
}

export interface SecretaryDashboard {
  metrics: SecretaryMetrics;
  orders: SecretaryOrder[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  updated_at: string;
  secretary_instances?: EvolutionInstance[];
  can_view_results: boolean;
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
  agent_type: AgentType;
  agent_enabled: boolean;
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
  tabela_preco_codigo?: string | null;
  tabela_preco_nome?: string | null;
  tabelas_especiais_json?: Array<{ produto: string; variacao: string; tabelaPreco: string }> | null;
}

export interface TabelaPreco {
  id?: number;
  codigo_tabela: string;
  nome_tabela?: string | null;
  synced_at?: string;
  total_itens?: number;
}

export interface TabelaPrecoItem {
  id?: number;
  codigo_tabela: string;
  cod_produto: string;
  nome_produto?: string | null;
  variacao?: string | null;
  quantidade_minima: number;
  preco: number;
  desconto: number;
  synced_at?: string;
}

export interface TabelasPrecoListResponse {
  tabelas: TabelaPreco[];
  total: number;
}

export interface TabelaPrecoItensResponse {
  codigo_tabela: string;
  nome_tabela: string | null;
  itens: TabelaPrecoItem[];
  total: number;
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

export interface RepresentanteOption {
  cod_rep: number;
  name: string;
  document: string | null;
  active: boolean;
  whatsapp_number: string | null;
  orders_count: number;
  customers_count: number;
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
  | "needs_review"
  | "dispatched"
  | "responded"
  | "converted"
  | "opted_out"
  | "activation_candidate"
  | "activation_approved"
  | "activation_rejected";

export interface RecorrenciaTarget {
  id: string;
  cpf_cnpj: string;
  customer_name: string | null;
  customer_phone: string | null;
  cod_rep: number | null;
  target_type: "recorrencia" | "ativacao";
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

export interface ResultadosPipelineStats {
  dispatched: number;
  converted: number;
  revenue: number;
}

export interface ResultadosStats {
  dispatched_total: number;
  converted_total: number;
  conversion_rate: number;
  revenue_total: number;
  by_pipeline: {
    recorrencia: ResultadosPipelineStats;
    ativacao: ResultadosPipelineStats;
  };
}

export interface ResultadosTarget extends RecorrenciaTarget {
  converted_at: string | null;
  converted_order_num: string | null;
  converted_order_value: number | null;
}

export interface ResultadosOverview {
  stats: ResultadosStats;
  targets: ResultadosTarget[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AtivacaoAiData {
  decisao?: string;
  tipo_abordagem?: string;
  nivel_confianca?: string;
  motivo?: string;
  mensagem?: string;
}

export interface AtivacaoOverview {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  stats: {
    activation_candidate: number;
    activation_approved: number;
    activation_rejected: number;
    dispatched: number;
  };
  targets: RecorrenciaTarget[];
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
    needs_review: number;
    dispatched: number;
    responded: number;
    converted: number;
    opted_out: number;
  };
  targets: RecorrenciaTarget[];
}

export type DisparoLogStatus = "success" | "partial" | "error" | "dry_run";

export interface DisparoLogError {
  id: string;
  nome: string;
  error: string;
}

export interface DisparoLog {
  id: string;
  flow: "recorrencia" | "ativacao";
  triggered_by: string;
  dry_run: boolean;
  processed: number;
  dispatched: number;
  skipped: number;
  errors_count: number;
  errors_json: DisparoLogError[];
  status: DisparoLogStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface DisparoLogsOverview {
  logs: DisparoLog[];
  total: number;
  page: number;
  pages: number;
}

export type ClicRequestLogStatus = "pending" | "success" | "error";

export interface ClicRequestLog {
  id: string;
  source: string;
  operation: string;
  endpoint: string;
  method: string;
  status: ClicRequestLogStatus;
  http_status?: number | null;
  order_id?: string | null;
  protocol?: string | null;
  cod_rep?: number | null;
  representative_document?: string | null;
  customer_code?: string | null;
  customer_document?: string | null;
  request_payload?: Record<string, unknown> | unknown[];
  response_payload?: Record<string, unknown> | unknown[] | null;
  error_message?: string | null;
  created_at: string;
  sent_at?: string | null;
  responded_at?: string | null;
  duration_ms?: number | null;
}

export interface ClicRequestLogsOverview {
  logs: ClicRequestLog[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  stats: Record<string, number>;
}

export type SecretaryMessageRole = "user" | "assistant" | "event";

export interface SecretaryMessage {
  id: string;
  conversation_id: string;
  external_message_id?: string | null;
  role: SecretaryMessageRole;
  content: string;
  payload_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface SecretaryConversation {
  id: string;
  conversation_key: string;
  instance_name: string;
  representative_phone: string;
  cod_rep: number;
  state_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  latest_message?: SecretaryMessage | null;
  error_hint?: string | null;
}

export interface SecretaryConversationDetail {
  conversation: SecretaryConversation;
  messages: SecretaryMessage[];
  orders: SecretaryOrder[];
  error_hint?: string | null;
}

export interface SecretaryConversationsOverview {
  conversations: SecretaryConversation[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ---------------------------------------------------------------------------
// Auth / RBAC
// ---------------------------------------------------------------------------

export type Role = "master_dev" | "admin" | "gestor" | "representante";

export interface UserProfile {
  id: string;
  role: Role;
  cod_rep: number | null;
  cpf: string | null;
  nome: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}
