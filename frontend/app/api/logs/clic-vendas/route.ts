import { NextResponse } from "next/server";
import { listClicRequestLogs } from "@/lib/server/clic-request-logs";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const result = await listClicRequestLogs({
      status: searchParams.get("status") || undefined,
      dateFrom: searchParams.get("date_from") || undefined,
      dateTo: searchParams.get("date_to") || undefined,
      search: searchParams.get("search") || undefined,
      page: Number(searchParams.get("page") || 1),
      pageSize: Number(searchParams.get("page_size") || 30),
    });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar logs do Clic Vendas" },
      { status: 500 }
    );
  }
}
