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

export const clicVendasApi = {
  sync: (dias = 30) =>
    api.post<{
      id: string;
      status: "success" | "error";
      message: string;
      total_fetched?: number;
      total_upserted?: number;
      duration_ms?: number;
    }>("/api/clic-vendas/sync", { dias, triggered_by: "manual" }),
  getSyncLogs: (date?: string) =>
    api.get<{ date: string; logs: import("./types").SyncLog[]; total: number }>(
      `/api/clic-vendas/sync-logs${date ? `?date=${date}` : ""}`
    ),
  getSyncLog: (id: string) => api.get(`/api/clic-vendas/sync-logs/${id}`),
  getPedidos: (params?: { cod_cli?: number; dias?: number; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.cod_cli) q.set("cod_cli", String(params.cod_cli));
    if (params?.dias) q.set("dias", String(params.dias));
    if (params?.page) q.set("page", String(params.page));

    return api.get<{
      total: number;
      page: number;
      pages: number;
      pedidos: import("./types").Pedido[];
    }>(`/api/clic-vendas/pedidos?${q}`);
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
  createInstance: (body: { name: string }) =>
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
    api.get<{ instanceName: string; agent_enabled: boolean }>(`/api/conexao/instances/${encodeURIComponent(name)}/agent`),
  toggleAgent: (name: string, enabled: boolean) =>
    api.post<{ instanceName: string; agent_enabled: boolean }>(`/api/conexao/instances/${encodeURIComponent(name)}/agent`, { enabled }),
};

export const clientesApi = {
  sync: (query?: string) =>
    api.post<import("./types").ClientesSyncResponse>("/api/clientes", {
      query: query || undefined,
    }),
  list: (params?: { query?: string; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.query) q.set("query", params.query);
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").ClientesListResponse>(
      `/api/clientes${q.size ? `?${q}` : ""}`
    );
  },
  detail: (codCli: number) =>
    api.get<import("./types").Cliente>(`/api/clientes/${codCli}`),
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
      last_run: string | null;
      last_run_status: "success" | "error" | null;
    }>("/api/clic-vendas/cron"),
  setEnabled: (enabled: boolean) =>
    api.post<{
      enabled: boolean;
      interval_hours: number;
      last_run: string | null;
      last_run_status: "success" | "error" | null;
    }>("/api/clic-vendas/cron", { enabled }),
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

export const revisaoPedidoApi = {
  list: (status?: string, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) params.set("status", status);
    return api.get<import("./types").PedidoRevisaoListResponse>(`/api/revisaopedido?${params}`);
  },
  detail: (id: string) =>
    api.get<import("./types").PedidoRevisao>(`/api/revisaopedido/${id}`),
  setStatus: (id: string, status: import("./types").PedidoRevisaoStatus) =>
    api.post<import("./types").PedidoRevisao>(`/api/revisaopedido/${id}/status`, { status }),
};
