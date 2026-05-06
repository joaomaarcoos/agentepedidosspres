import { NextResponse } from "next/server";
import { runPythonJson } from "@/lib/server/python";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PythonEnvelope<T> = { ok: true; data: T } | { ok: false; error: string };

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const limit: number = Number(body.limit ?? 20);
    const id: string | undefined = body.id;

    const args = ["run", "--limit", String(limit)];
    if (id) args.push("--id", id);

    const result = await runPythonJson<PythonEnvelope<{
      processed: number;
      approved: number;
      rejected: number;
      errors: { id: string; nome: string; error: string }[];
    }>>("execution/agent_validacao_recompra.py", args);

    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: 500 });
    }
    return NextResponse.json(result.data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao rodar agente de validação" },
      { status: 500 }
    );
  }
}
