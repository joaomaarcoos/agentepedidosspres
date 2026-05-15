import { NextResponse } from "next/server";
import { listProdutos } from "@/lib/server/produtos";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const filial = searchParams.get("filial") || undefined;
    const busca = searchParams.get("busca") || undefined;

    const result = await listProdutos({ filial, busca });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar produtos" },
      { status: 500 }
    );
  }
}
