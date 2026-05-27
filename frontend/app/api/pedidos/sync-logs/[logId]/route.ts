import { NextResponse } from "next/server";
import { getPedidosSyncLog } from "@/lib/server/pedidos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: { logId: string } }
) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const result = await getPedidosSyncLog(context.params.logId);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Erro interno ao buscar log";
    const status = message.toLowerCase().includes("não encontrado") ? 404 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
