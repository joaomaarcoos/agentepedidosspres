import { runPythonJson } from "@/lib/server/python";
import type { ProdutosListResponse } from "@/lib/types";

export async function listProdutos(params?: { filial?: string; busca?: string }) {
  const args: string[] = [];
  if (params?.filial) args.push("--filial", params.filial);
  if (params?.busca) args.push("--busca", params.busca);

  const result = await runPythonJson<ProdutosListResponse>("execution/produtos_cli.py", args);
  if (!result.ok) throw new Error("Erro ao buscar produtos");
  return result;
}
