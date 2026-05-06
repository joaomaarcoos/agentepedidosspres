import { runPythonJson } from "@/lib/server/python";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callClicVendas<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/clic_vendas_cli.py", args);

  if (!result.ok) {
    throw new Error(result.error);
  }

  return result.data;
}

export function syncClicVendas(dias: number, triggeredBy: string) {
  return callClicVendas<{
    id: string;
    status: "success" | "error";
    message: string;
    total_fetched?: number;
    total_upserted?: number;
    duration_ms?: number;
  }>(["sync", "--dias", String(dias), "--triggered-by", triggeredBy]);
}

export function listClicVendasSyncLogs(date?: string, limit = 50) {
  const args = ["sync-logs", "--limit", String(limit)];
  if (date) {
    args.push("--date", date);
  }

  return callClicVendas<{
    date: string;
    logs: Array<Record<string, unknown>>;
    total: number;
  }>(args);
}

export function getClicVendasSyncLog(logId: string) {
  return callClicVendas<Record<string, unknown>>(["sync-log", "--log-id", logId]);
}

export function listClicVendasPedidos(params: {
  codCli?: number;
  dias?: number;
  page?: number;
  pageSize?: number;
}) {
  const args = ["pedidos"];

  if (params.codCli !== undefined) {
    args.push("--cod-cli", String(params.codCli));
  }
  if (params.dias !== undefined) {
    args.push("--dias", String(params.dias));
  }
  if (params.page !== undefined) {
    args.push("--page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    args.push("--page-size", String(params.pageSize));
  }

  return callClicVendas<{
    total: number;
    page: number;
    page_size: number;
    pages: number;
    pedidos: Array<Record<string, unknown>>;
  }>(args);
}
