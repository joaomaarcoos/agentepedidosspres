import { NextResponse } from "next/server";
import { getPedidoDetail } from "@/lib/server/revisaopedido";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
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
