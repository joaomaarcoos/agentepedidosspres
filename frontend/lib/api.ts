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

export const conexaoApi = {
  status: () => api.get<import("./types").ConexaoStatus>("/api/conexao/status"),
  listInstances: () => api.get<import("./types").EvolutionInstancesResponse>("/api/conexao/instances"),
  createInstance: (body: { name: string; webhookUrl?: string; msgCall?: string }) =>
    api.post<import("./types").CreateInstanceResult>("/api/conexao/instances", body),
  getQrCode: (name: string) =>
    api.get<import("./types").QrCodeResult>(`/api/conexao/instances/${encodeURIComponent(name)}/qrcode`),
  deleteInstance: (name: string) =>
    api.delete<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}`),
  disconnectInstance: (name: string) =>
    api.post<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}/disconnect`),
  restartInstance: (name: string) =>
    api.post<import("./types").InstanceActionResult>(`/api/conexao/instances/${encodeURIComponent(name)}/restart`),
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
  list: (params?: { dias?: number; minPedidos?: number; page?: number; pageSize?: number }) => {
    const q = new URLSearchParams();
    if (params?.dias) q.set("dias", String(params.dias));
    if (params?.minPedidos) q.set("min_pedidos", String(params.minPedidos));
    if (params?.page) q.set("page", String(params.page));
    if (params?.pageSize) q.set("page_size", String(params.pageSize));
    return api.get<import("./types").RecorrenciaOverview>(
      `/api/recorrencia${q.size ? `?${q}` : ""}`
    );
  },
  detail: (codCli: number, dias = 180) =>
    api.get<import("./types").RecorrenciaCliente>(
      `/api/recorrencia/${codCli}?dias=${dias}`
    ),
};
