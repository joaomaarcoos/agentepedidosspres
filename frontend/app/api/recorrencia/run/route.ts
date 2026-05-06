import { NextResponse } from "next/server";
import { runRecorrenciaScript } from "@/lib/server/recorrencia";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const result = await runRecorrenciaScript();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao rodar script de recompra" },
      { status: 500 }
    );
  }
}
