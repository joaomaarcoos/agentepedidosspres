import { NextResponse } from "next/server";
import { runDispatch } from "@/lib/server/recorrencia";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const dryRun: boolean = body.dry_run ?? false;
    const limit: number = Number(body.limit ?? 50);

    const result = await runDispatch(dryRun, limit);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao executar disparos" },
      { status: 500 }
    );
  }
}
