import { NextResponse } from "next/server";
import { listPedidosSyncLogs } from "@/lib/server/pedidos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get("date") || undefined;
    const limit = Number(searchParams.get("limit") ?? 50);

    if (!Number.isFinite(limit) || limit < 1 || limit > 200) {
      return NextResponse.json({ error: "Parâmetro limit inválido" }, { status: 400 });
    }

    const result = await listPedidosSyncLogs(date, limit);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar logs" },
      { status: 500 }
    );
  }
}
