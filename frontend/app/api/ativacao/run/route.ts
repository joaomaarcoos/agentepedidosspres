import { NextResponse } from "next/server";
import { runAtivacaoScript } from "@/lib/server/ativacao";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json().catch(() => ({}));
    const dryRun: boolean = body.dry_run ?? false;
    const limit: number = Number(body.limit ?? 100);

    const result = await runAtivacaoScript(dryRun, limit);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao gerar candidatos de ativação" },
      { status: 500 }
    );
  }
}
