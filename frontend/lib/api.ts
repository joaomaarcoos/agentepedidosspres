const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export const pedidosApi = {
  sync: (dias = 30, repDocument?: string) =>
    api.post<{
      id: string;
      status: "success" | "error";
      message: string;
      total_fetched?: number;
      total_upserted?: number;
      duration_ms?: number;
    }>("/api/pedidos/sync", { dias, triggered_by: "manual", rep_document: repDocument }),
  getSyncLogs: (date?: string) =>
    api.get<{ date: string; logs: import("./types").SyncLog[]; total: number }>(
      `/api/pedidos/sync-logs${date ? `?date=${date}` : ""}`
    ),
  getSyncLog: (id: string) => api.get(`/api/pedidos/sync-logs/${id}`),
  list: (params?: { cod_cli?: number; cod_rep?: number; dias?: number; page?: number; origin?: "all" | "ia_secretaria" }) => {
    const q = new URLSearchParams();
    if (params?.cod_cli) q.set("cod_cli", String(params.cod_cli));
    if (params?.cod_rep) q.set("cod_rep", String(params.cod_rep));
    if (params?.dias) q.set("dias", String(params.dias));
    if (params?.page) q.set("page", String(params.page));
    if (params?.origin && params.origin !== "all") q.set("origin", params.origin);
    return api.get<{
      total: number;
      page: number;
      pages: number;
      metrics?: {
        unique_clients: number;
        total_value: number;
        metrics_limit?: number;
        metrics_truncated?: boolean;
      };
      pedidos: import("./types").Pedido[];
    }>(`/api/pedidos?${q}`);
  },
};

export const statusApi = {
  check: () => api.get<import("./types").ApiStatus>("/api/status"),
};

export const produtosApi = {
  list: (params?: { filial?: string; busca?: string }) => {
    const q = new URLSearchParams();
    if (params?.filial) q.set("filial", params.filial);
    if (params?.busca) q.set("busca", params.busca);
    return api.get<import("./types").ProdutosListResponse>(`/api/produtos?${q}`);
  },
};

export const conexaoApi = {
  status: () => api.get<import("./types").ConexaoStatus>("/api/conexao/status"),
  listInstances: () => api.get<import("./types").EvolutionInstancesResponse>("/api/conexao/instances"),
  createInstance: (body: { name: string; agent_type: import("./types").AgentType }) =>
    api.post<import("./types").CreateInstanceResult>("/api/conexao/instances", body),
  getQrCode: (name: string) =>
    api.get<import("./types").QrCodeResult>(`/api/conexao/instances/${encodeURIComponent(name)}/qrcode`),
  deleteInstance: (name: string) =>
    api.delete<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}`),
  disconnectInstance: (name: string) =>
    api.post<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}/disconnect`),
  restartInstance: (name: string) =>
    api.post<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}/restart`),
  getAgentStatus: (name: string) =>
    api.get<{ instanceName: string; agent_enabled: boolean; agent_type: import("./types").AgentType }>(`/api/conexao/instances/${encodeURIComponent(name)}/agent`),
  toggleAgent: (name: string, enabled: boolean) =>
    api.post<{ instanceName: string; agent_enabled: boolean }>(`/api/conexao/instances/${encodeURIComponent(name)}/agent`, { enabled }),
};

export const clientesApi = {
  sync: (query?: string) =>
    api.post<import("./types").ClientesSyncResponse>("/api/clientes", {
      query: query || undefined,
    }),
  list: (params?: { query?: string; cod_rep?: number; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.query) q.set("query", params.query);
    if (params?.cod_rep) q.set("cod_rep", String(params.cod_rep));
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").ClientesListResponse>(
      `/api/clientes${q.size ? `?${q}` : ""}`
    );
  },
  detail: (codCli: number, params?: { cod_rep?: number }) => {
    const q = new URLSearchParams();
    if (params?.cod_rep) q.set("cod_rep", String(params.cod_rep));
    return api.get<import("./types").Cliente>(`/api/clientes/${codCli}${q.size ? `?${q}` : ""}`);
  },
};

export const representantesApi = {
  list: () =>
    api.get<{ representantes: import("./types").RepresentanteOption[] }>("/api/representantes"),
};

export const recorrenciaApi = {
  list: (params?: { status?: string; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").RecorrenciaOverview>(
      `/api/recorrencia${q.size ? `?${q}` : ""}`
    );
  },
  detail: (id: string) =>
    api.get<import("./types").RecorrenciaTarget>(`/api/recorrencia/${id}`),
  runScript: () =>
    api.post<{
      inserted: number;
      updated: number;
      skipped: number;
      skipped_invalid_orders: number;
      errors: { cpf_cnpj: string; error: string }[];
      dry_run: boolean;
    }>("/api/recorrencia/run"),
  validate: (params?: { limit?: number; id?: string }) =>
    api.post<{
      processed: number;
      approved: number;
      rejected: number;
      needs_review: number;
      errors: { id: string; nome: string; error: string }[];
    }>("/api/recorrencia/validate", params),
  dispatch: (dryRun = false) =>
    api.post<{
      processed: number;
      dispatched: number;
      skipped: number;
      errors: { id: string; nome: string; error: string }[];
      dry_run: boolean;
    }>("/api/recorrencia/dispatch", { dry_run: dryRun }),
  pipeline: (triggeredBy: "manual" | "schedule" | "auto" = "manual", dryRun = false, skipDispatch = false) =>
    api.post<{
      triggered_by: string;
      dry_run: boolean;
      skip_dispatch: boolean;
      script: { inserted: number; updated: number; skipped: number; errors: unknown[] };
      validate: { processed: number; approved: number; rejected: number; needs_review: number; errors: unknown[] };
      dispatch: { processed: number; dispatched: number; skipped: number; errors: unknown[]; dry_run: boolean };
    }>("/api/recorrencia/pipeline", { triggered_by: triggeredBy, dry_run: dryRun, skip_dispatch: skipDispatch }),
};

export const resultadosApi = {
  list: (params?: { targetType?: "all" | "recorrencia" | "ativacao"; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.targetType) q.set("target_type", params.targetType);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").ResultadosOverview>(
      `/api/resultados${q.size ? `?${q}` : ""}`
    );
  },
};

export const secretariaApi = {
  dashboard: (params?: {
    dateFrom?: string;
    dateTo?: string;
    status?: import("./types").SecretaryOrderStatus | "all";
    search?: string;
    page?: number;
    pageSize?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.dateFrom) q.set("date_from", params.dateFrom);
    if (params?.dateTo) q.set("date_to", params.dateTo);
    if (params?.status && params.status !== "all") q.set("status", params.status);
    if (params?.search) q.set("search", params.search);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").SecretaryDashboard>(
      `/api/secretaria${q.size ? `?${q}` : ""}`
    );
  },
  listConversations: (params?: { search?: string; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set("search", params.search);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").SecretaryConversationsOverview>(
      `/api/secretaria/conversas${q.size ? `?${q}` : ""}`
    );
  },
  getConversation: (id: string) =>
    api.get<import("./types").SecretaryConversationDetail>(
      `/api/secretaria/conversas/${encodeURIComponent(id)}`
    ),
};

export const saidaProdutosApi = {
  list: (params?: { year?: number; periodCount?: 2 | 3 | 4; limit?: number; cod_rep?: number }) => {
    const q = new URLSearchParams();
    if (params?.year) q.set("year", String(params.year));
    if (params?.periodCount) q.set("period_count", String(params.periodCount));
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.cod_rep) q.set("cod_rep", String(params.cod_rep));
    return api.get<import("./types").PrevisaoOverview>(
      `/api/saida-produtos${q.size ? `?${q}` : ""}`
    );
  },
};

export const logsApi = {
  listDisparo: (params?: { flow?: string; status?: string; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.flow) q.set("flow", params.flow);
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").DisparoLogsOverview>(
      `/api/logs/disparo${q.size ? `?${q}` : ""}`
    );
  },
  getDisparo: (id: string) =>
    api.get<import("./types").DisparoLog>(`/api/logs/disparo/${id}`),
  listRequisitionLogs: (params?: {
    status?: import("./types").RequisitionLogStatus | "all";
    dateFrom?: string;
    dateTo?: string;
    search?: string;
    page?: number;
    pageSize?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== "all") q.set("status", params.status);
    if (params?.dateFrom) q.set("date_from", params.dateFrom);
    if (params?.dateTo) q.set("date_to", params.dateTo);
    if (params?.search) q.set("search", params.search);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").RequisitionLogsOverview>(
      `/api/logs/requisitions${q.size ? `?${q}` : ""}`
    );
  },
  getRequisitionLog: (id: string) =>
    api.get<import("./types").RequisitionLog>(`/api/logs/requisitions/${id}`),
};

export const settingsApi = {
  getDisparo: () =>
    api.get<{ disparo_recorrencia: boolean; disparo_ativacao: boolean }>("/api/settings/disparo"),
  setDisparo: (key: "disparo_recorrencia_enabled" | "disparo_ativacao_enabled", value: boolean) =>
    api.patch<{ key: string; value: boolean }>("/api/settings/disparo", { key, value }),
};

export const cronApi = {
  getStatus: () =>
    api.get<{
      enabled: boolean;
      interval_hours: number;
      dias?: number;
      rep_document?: string | null;
      rep_documents?: string[];
      last_run: string | null;
      last_run_status: "success" | "error" | null;
    }>("/api/pedidos/cron"),
  setEnabled: (enabled: boolean, options?: { dias?: number; repDocument?: string | null; repDocuments?: string[] }) =>
    api.post<{
      enabled: boolean;
      interval_hours: number;
      dias?: number;
      rep_document?: string | null;
      rep_documents?: string[];
      last_run: string | null;
      last_run_status: "success" | "error" | null;
    }>("/api/pedidos/cron", {
      enabled,
      dias: options?.dias,
      rep_document: options?.repDocument,
      rep_documents: options?.repDocuments,
    }),
};

export const ativacaoApi = {
  list: (params?: { status?: string; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").AtivacaoOverview>(
      `/api/ativacao${q.size ? `?${q}` : ""}`
    );
  },
  detail: (id: string) =>
    api.get<import("./types").RecorrenciaTarget>(`/api/ativacao/${id}`),
  runScript: (dryRun = false) =>
    api.post<{
      processed: number;
      eligible: number;
      skipped_cooldown: number;
      skipped_no_data: number;
      inserted: number;
      updated: number;
      errors: { cpf_cnpj: string; error: string }[];
      dry_run: boolean;
    }>("/api/ativacao/run", { dry_run: dryRun }),
  validate: (params?: { limit?: number; id?: string }) =>
    api.post<{
      processed: number;
      approved: number;
      rejected: number;
      errors: { id: string; nome: string; error: string }[];
    }>("/api/ativacao/validate", params),
  pipeline: (triggeredBy: "manual" | "schedule" | "auto" = "manual", dryRun = false) =>
    api.post<{
      triggered_by: string;
      dry_run: boolean;
      script: { processed: number; eligible: number; inserted: number; updated: number; errors: unknown[] };
      validate: { processed: number; approved: number; rejected: number; errors: unknown[] };
    }>("/api/ativacao/pipeline", { triggered_by: triggeredBy, dry_run: dryRun }),
};

export const agenteStudioApi = {
  list: () => api.get<{ prompts: import("./types").PromptFile[] }>("/api/agente-studio/prompts"),
  get: (slug: string) => api.get<import("./types").PromptFile>(`/api/agente-studio/prompts/${slug}`),
  getSettings: () =>
    api.get<{ message_buffer_seconds: number }>("/api/agente-studio/settings"),
  updateSettings: (settings: { message_buffer_seconds: number }) =>
    api.patch<{ message_buffer_seconds: number }>("/api/agente-studio/settings", settings),
  create: (slug: string, content: string) =>
    api.post<import("./types").PromptFile>("/api/agente-studio/prompts", { slug, content }),
  update: (slug: string, content: string) =>
    request<import("./types").PromptFile>(`/api/agente-studio/prompts/${slug}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  delete: (slug: string) =>
    api.delete<{ ok: boolean }>(`/api/agente-studio/prompts/${slug}`),
};

export const tabelaPrecoApi = {
  list: () =>
    api.get<import("./types").TabelasPrecoListResponse>("/api/tabela-preco"),
  getItens: (codigoTabela: string) =>
    api.get<import("./types").TabelaPrecoItensResponse>(
      `/api/tabela-preco?tabela=${encodeURIComponent(codigoTabela)}`
    ),
  sync: (codigos: string[] = ["201", "202"]) =>
    api.post<{ ok: boolean; data: { tabelas_upserted: number; itens_upserted: number; duration_ms: number } }>(
      "/api/tabela-preco",
      { codigos }
    ),
};

export const revisaoPedidoApi = {
  list: (status?: string, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    return api.get<import("./types").PedidoRevisaoListResponse>(`/api/revisaopedido?${params}`);
  },
  detail: (id: string) =>
    api.get<import("./types").PedidoRevisao>(`/api/revisaopedido/${id}`),
  update: (
    id: string,
    body: { itens_json: import("./types").PedidoRevisaoItem[]; observacoes: string }
  ) =>
    api.patch<import("./types").PedidoRevisao>(`/api/revisaopedido/${id}`, body),
  setStatus: (id: string, status: import("./types").PedidoRevisaoStatus) =>
    api.post<import("./types").PedidoRevisao>(`/api/revisaopedido/${id}/status`, { status }),
};
