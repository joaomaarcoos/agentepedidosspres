import { NextResponse } from "next/server";
import { runPipeline } from "@/lib/server/recorrencia";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json().catch(() => ({}));
    const dryRun: boolean = body.dry_run ?? false;
    const triggeredBy: "manual" | "schedule" | "auto" =
      body.triggered_by ?? "manual";
    const skipDispatch: boolean = body.skip_dispatch ?? false;

    const result = await runPipeline(dryRun, triggeredBy, skipDispatch);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao executar pipeline" },
      { status: 500 }
    );
  }
}
