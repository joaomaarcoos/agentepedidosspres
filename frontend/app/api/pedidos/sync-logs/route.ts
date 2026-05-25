import { NextResponse } from "next/server";
import { listPedidosSyncLogs } from "@/lib/server/pedidos";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
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
