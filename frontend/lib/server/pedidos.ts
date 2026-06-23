import { runPythonJson } from "@/lib/server/python";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callPedidos<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/clic_vendas_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function syncPedidos(dias: number, triggeredBy: string, repDocument?: string) {
  const args = ["sync", "--dias", String(dias), "--triggered-by", triggeredBy];
  if (repDocument) args.push("--rep-document", repDocument);
  return callPedidos<{
    id: string;
    status: "success" | "error";
    message: string;
    total_fetched?: number;
    total_upserted?: number;
    duration_ms?: number;
  }>(args);
}

export function listPedidosSyncLogs(date?: string, limit = 50) {
  const args = ["sync-logs", "--limit", String(limit)];
  if (date) args.push("--date", date);
  return callPedidos<{
    date: string;
    logs: Array<Record<string, unknown>>;
    total: number;
  }>(args);
}

export function getPedidosSyncLog(logId: string) {
  return callPedidos<Record<string, unknown>>(["sync-log", "--log-id", logId]);
}

export function listPedidos(params: {
  codCli?: number;
  codRep?: number;
  dias?: number;
  page?: number;
  pageSize?: number;
}) {
  const args = ["pedidos"];
  if (params.codCli !== undefined) args.push("--cod-cli", String(params.codCli));
  if (params.codRep !== undefined) args.push("--cod-rep", String(params.codRep));
  if (params.dias !== undefined) args.push("--dias", String(params.dias));
  if (params.page !== undefined) args.push("--page", String(params.page));
  if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
  return callPedidos<{
    total: number;
    page: number;
    page_size: number;
    pages: number;
    pedidos: Array<Record<string, unknown>>;
  }>(args);
}

export function getSaidaProdutos(params: {
  year?: number;
  periodCount?: number;
  limit?: number;
  codRep?: number;
}) {
  const args = ["previsao"];
  if (params.year !== undefined) args.push("--year", String(params.year));
  if (params.periodCount !== undefined) args.push("--period-count", String(params.periodCount));
  if (params.limit !== undefined) args.push("--limit", String(params.limit));
  if (params.codRep !== undefined) args.push("--cod-rep", String(params.codRep));
  return callPedidos<Record<string, unknown>>(args);
}
