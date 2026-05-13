import { NextResponse } from "next/server";
import { runAtivacaoPipeline } from "@/lib/server/ativacao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const dryRun: boolean = body.dry_run ?? false;
    const triggeredBy: "manual" | "schedule" | "auto" =
      body.triggered_by ?? "manual";

    const result = await runAtivacaoPipeline(dryRun, triggeredBy);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao executar pipeline de ativação" },
      { status: 500 }
    );
  }
}
