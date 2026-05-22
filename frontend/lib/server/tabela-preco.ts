import { runPythonJson } from "@/lib/server/python";
import type { TabelasPrecoListResponse, TabelaPrecoItensResponse } from "@/lib/types";

type PythonEnvelope<T> = { ok: true; data: T } | { ok: false; error: string };

async function callTabela<T>(args: string[]): Promise<T> {
  const result = await runPythonJson<PythonEnvelope<T>>(
    "execution/tabela_preco_cli.py",
    args,
    { timeoutMs: 2 * 60 * 1000 }
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function listTabelasPreco(): Promise<TabelasPrecoListResponse> {
  return callTabela<TabelasPrecoListResponse>(["list"]);
}

export function getTabelaItens(codigoTabela: string): Promise<TabelaPrecoItensResponse> {
  return callTabela<TabelaPrecoItensResponse>(["detail", "--cod-tpr", codigoTabela]);
}

export function syncTabelasPreco(codigos: string[] = ["201", "202"]): Promise<{
  tabelas_upserted: number;
  itens_upserted: number;
  duration_ms: number;
  codigos_solicitados?: string[];
  erros?: { cod_tpr: string; erro: string }[];
}> {
  return callTabela(["sync", "--cod-tpr", ...codigos]);
}
