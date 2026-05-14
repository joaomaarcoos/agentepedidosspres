import { NextResponse } from "next/server";
import { setPedidoStatus } from "@/lib/server/revisaopedido";
import type { PedidoRevisaoStatus } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const result = await setPedidoStatus(params.id, body.status as PedidoRevisaoStatus);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao atualizar status" },
      { status: 500 }
    );
  }
}
