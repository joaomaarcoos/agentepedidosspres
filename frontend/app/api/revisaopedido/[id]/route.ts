import { NextResponse } from "next/server";
import { getPedidoDetail, updatePedido } from "@/lib/server/revisaopedido";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const result = await getPedidoDetail(params.id);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar pedido" },
      { status: 500 }
    );
  }
}

export async function PATCH(
  request: Request,
  { params }: { params: { id: string } }
) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json();
    const result = await updatePedido(params.id, {
      itens_json: Array.isArray(body.itens_json) ? body.itens_json : [],
      observacoes: String(body.observacoes ?? ""),
    });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao editar pedido" },
      { status: 500 }
    );
  }
}
