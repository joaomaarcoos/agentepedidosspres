import { runPythonJson } from "@/lib/server/python";
import type { ResultadosOverview } from "@/lib/types";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callResultados<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/resultados_cli.py", args);
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

export function listResultados(params: {
  targetType?: "all" | "recorrencia" | "ativacao";
  page?: number;
  pageSize?: number;
}) {
  const args = ["overview"];
  if (params.targetType) args.push("--target-type", params.targetType);
  if (params.page !== undefined) args.push("--page", String(params.page));
  if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
  return callResultados<ResultadosOverview>(args);
}
