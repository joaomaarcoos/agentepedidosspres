import { runPythonJson } from "@/lib/server/python";
import type { AtivacaoOverview, RecorrenciaTarget } from "@/lib/types";

type PythonEnvelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function callAtivacao<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>("execution/ativacao_cli.py", args);
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

async function callValidateAtivacao<T>(args: string[]) {
  const result = await runPythonJson<PythonEnvelope<T>>(
    "execution/agent_validacao_ativacao.py",
    args
  );
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

export function listAtivacao(params: {
  status?: string;
  page?: number;
  pageSize?: number;
}) {
  const args = ["overview"];
  if (params.status) args.push("--status", params.status);
  if (params.page !== undefined) args.push("--page", String(params.page));
  if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
  return callAtivacao<AtivacaoOverview>(args);
}

export function getAtivacaoTarget(params: { id: string }) {
  return callAtivacao<RecorrenciaTarget>(["detail", "--id", params.id]);
}

export function runAtivacaoScript(dryRun = false, limit = 100) {
  const args = ["run"];
  if (dryRun) args.push("--dry-run");
  args.push("--limit", String(limit));
  return callAtivacao<{
    processed: number;
    eligible: number;
    skipped_cooldown: number;
    skipped_no_data: number;
    inserted: number;
    updated: number;
    errors: { cpf_cnpj: string; error: string }[];
    dry_run: boolean;
  }>(args);
}

export function runValidacaoAtivacao(params: { limit?: number; id?: string }) {
  const args = ["run"];
  if (params.limit !== undefined) args.push("--limit", String(params.limit));
  if (params.id) args.push("--id", params.id);
  return callValidateAtivacao<{
    processed: number;
    approved: number;
    rejected: number;
    errors: { id: string; nome: string; error: string }[];
  }>(args);
}

export async function runAtivacaoPipeline(
  dryRun = false,
  triggeredBy: "manual" | "schedule" | "auto" = "manual"
) {
  const scriptResult = await runAtivacaoScript(dryRun);
  const validateResult = await runValidacaoAtivacao({ limit: 50 });

  return {
    triggered_by: triggeredBy,
    dry_run: dryRun,
    script: scriptResult,
    validate: validateResult,
  };
}
