import { NextResponse } from "next/server";
import { syncPedidos } from "@/lib/server/pedidos";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const dias = Number(body?.dias ?? 30);
    const triggeredBy = String(body?.triggered_by ?? "manual");

    if (!Number.isFinite(dias) || dias < 1 || dias > 365) {
      return NextResponse.json({ error: "Parâmetro dias inválido" }, { status: 400 });
    }

    const result = await syncPedidos(dias, triggeredBy);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao sincronizar" },
      { status: 500 }
    );
  }
}
