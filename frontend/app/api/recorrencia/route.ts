import { NextResponse } from "next/server";
import { listRecorrencia } from "@/lib/server/recorrencia";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const dias = Number(searchParams.get("dias") ?? 180);
    const minPedidos = Number(searchParams.get("min_pedidos") ?? 2);
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 50);

    if (!Number.isFinite(dias) || dias < 1 || dias > 730) {
      return NextResponse.json({ error: "Parâmetro dias inválido" }, { status: 400 });
    }
    if (!Number.isFinite(minPedidos) || minPedidos < 1 || minPedidos > 20) {
      return NextResponse.json({ error: "Parâmetro min_pedidos inválido" }, { status: 400 });
    }
    if (!Number.isFinite(page) || page < 1) {
      return NextResponse.json({ error: "Parâmetro page inválido" }, { status: 400 });
    }
    if (!Number.isFinite(pageSize) || pageSize < 1 || pageSize > 200) {
      return NextResponse.json({ error: "Parâmetro page_size inválido" }, { status: 400 });
    }

    const result = await listRecorrencia({ dias, minPedidos, page, pageSize });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao calcular recorrência" },
      { status: 500 }
    );
  }
}
