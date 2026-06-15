import { NextResponse } from "next/server";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";
import { getSecretaryMetrics } from "@/lib/server/secretaria";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;
  try {
    const { searchParams } = new URL(request.url);
    const data = await getSecretaryMetrics(
      searchParams.get("date_from") || undefined,
      searchParams.get("date_to") || undefined
    );
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar metricas" },
      { status: 500 }
    );
  }
}

