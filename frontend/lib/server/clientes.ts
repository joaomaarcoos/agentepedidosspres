import { runPythonJson } from "@/lib/server/python";
import type { Cliente, ClientesListResponse, ClientesSyncResponse } from "@/lib/types";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callClientes<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/clientes_cli.py", args);
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

export function syncClientes(query?: string) {
  const args = ["sync"];
  if (query) {
    args.push("--query", query);
  }
  return callClientes<ClientesSyncResponse>(args);
}

export function listClientes(params: { query?: string; page?: number; pageSize?: number }) {
  const args = ["list"];
  if (params.query) {
    args.push("--query", params.query);
  }
  if (params.page !== undefined) {
    args.push("--page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    args.push("--page-size", String(params.pageSize));
  }
  return callClientes<ClientesListResponse>(args);
}

export function getCliente(codCli: number) {
  return callClientes<Cliente>(["detail", "--cod-cli", String(codCli)]);
}
