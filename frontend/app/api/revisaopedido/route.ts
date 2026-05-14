import { NextResponse } from "next/server";
import { listPedidos } from "@/lib/server/revisaopedido";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get("status") || undefined;
    const page = parseInt(searchParams.get("page") ?? "1");
    const pageSize = parseInt(searchParams.get("page_size") ?? "50");
    const result = await listPedidos(status, page, pageSize);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao listar pedidos" },
      { status: 500 }
    );
  }
}
