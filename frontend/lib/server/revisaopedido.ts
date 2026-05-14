import { runPythonJson } from "@/lib/server/python";
import type { PedidoRevisao, PedidoRevisaoListResponse, PedidoRevisaoStatus } from "@/lib/types";

type Envelope<T> = { ok: true; data: T } | { ok: false; error: string };

async function call<T>(args: string[]): Promise<T> {
  const result = await runPythonJson<Envelope<T>>("execution/revisaopedido_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function listPedidos(status?: string, page = 1, pageSize = 50) {
  const args = ["list", "--page", String(page), "--page-size", String(pageSize)];
  if (status) args.push("--status", status);
  return call<PedidoRevisaoListResponse>(args);
}

export function getPedidoDetail(id: string) {
  return call<PedidoRevisao>(["detail", "--id", id]);
}

export function setPedidoStatus(id: string, status: PedidoRevisaoStatus) {
  return call<PedidoRevisao>(["set-status", "--id", id, "--status", status]);
}
