import { runPythonJson } from "@/lib/server/python";
import type { RecorrenciaOverview, RecorrenciaTarget } from "@/lib/types";

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
  status?: string;
  page?: number;
  pageSize?: number;
}) {
  const args = ["overview"];
  if (params.status) args.push("--status", params.status);
  if (params.page !== undefined) args.push("--page", String(params.page));
  if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
  return callRecorrencia<RecorrenciaOverview>(args);
}

export function getRecorrenciaTarget(params: { cpf?: string; id?: string }) {
  const args = ["detail"];
  if (params.id) args.push("--id", params.id);
  else if (params.cpf) args.push("--cpf", params.cpf);
  return callRecorrencia<RecorrenciaTarget>(args);
}

export function runRecorrenciaScript(dryRun = false) {
  const args = ["run"];
  if (dryRun) args.push("--dry-run");
  return callRecorrencia<{
    inserted_or_updated: number;
    skipped: number;
    errors: { cpf_cnpj: string; error: string }[];
    dry_run: boolean;
  }>(args);
}
