import { runPythonJson } from "@/lib/server/python";
import type { RecorrenciaCliente, RecorrenciaOverview } from "@/lib/types";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callRecorrencia<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/recorrencia_cli.py", args);
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

export function listRecorrencia(params: {
  dias?: number;
  minPedidos?: number;
  page?: number;
  pageSize?: number;
}) {
  const args = ["overview"];
  if (params.dias !== undefined) {
    args.push("--dias", String(params.dias));
  }
  if (params.minPedidos !== undefined) {
    args.push("--min-pedidos", String(params.minPedidos));
  }
  if (params.page !== undefined) {
    args.push("--page", String(params.page));
  }
  if (params.pageSize !== undefined) {
    args.push("--page-size", String(params.pageSize));
  }
  return callRecorrencia<RecorrenciaOverview>(args);
}

export function getRecorrenciaCliente(codCli: number, dias = 180) {
  return callRecorrencia<RecorrenciaCliente>([
    "detail",
    "--cod-cli",
    String(codCli),
    "--dias",
    String(dias),
  ]);
}
