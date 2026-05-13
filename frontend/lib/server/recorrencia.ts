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

async function callValidate<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>(
    "execution/agent_validacao_recorrencia.py",
    args
  );
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

async function callDispatch<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>(
    "execution/disparos_recorrencia.py",
    args
  );
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
    inserted: number;
    updated: number;
    skipped: number;
    skipped_invalid_orders: number;
    errors: { cpf_cnpj: string; error: string }[];
    dry_run: boolean;
  }>(args);
}

export function runValidacao(params: { limit?: number; id?: string }) {
  const args = ["run"];
  if (params.limit !== undefined) args.push("--limit", String(params.limit));
  if (params.id) args.push("--id", params.id);
  return callValidate<{
    processed: number;
    approved: number;
    rejected: number;
    needs_review: number;
    errors: { id: string; nome: string; error: string }[];
  }>(args);
}

export function runDispatch(dryRun = false, limit = 50) {
  const args = ["run"];
  if (dryRun) args.push("--dry-run");
  args.push("--limit", String(limit));
  return callDispatch<{
    processed: number;
    dispatched: number;
    skipped: number;
    errors: { id: string; nome: string; error: string }[];
    dry_run: boolean;
  }>(args);
}

export async function runPipeline(
  dryRun = false,
  triggeredBy: "manual" | "schedule" | "auto" = "manual",
  skipDispatch = false
) {
  const scriptResult = await runRecorrenciaScript(dryRun);
  const validateResult = await runValidacao({ limit: 50 });
  const dispatchResult = skipDispatch
    ? { processed: 0, dispatched: 0, skipped: 0, errors: [], dry_run: true }
    : await runDispatch(dryRun);

  return {
    triggered_by: triggeredBy,
    dry_run: dryRun,
    skip_dispatch: skipDispatch,
    script: scriptResult,
    validate: validateResult,
    dispatch: dispatchResult,
  };
}
