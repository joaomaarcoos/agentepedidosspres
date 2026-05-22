import { NextResponse } from "next/server";
import { listTabelasPreco, getTabelaItens, syncTabelasPreco } from "@/lib/server/tabela-preco";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const tabela = searchParams.get("tabela");

    if (tabela) {
      const result = await getTabelaItens(tabela);
      return NextResponse.json(result);
    }

    const result = await listTabelasPreco();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar tabelas de preço" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as { codigos?: string[] };
    const result = await syncTabelasPreco(body.codigos ?? ["201", "202"]);
    return NextResponse.json({ ok: true, data: result });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao sincronizar tabelas de preço" },
      { status: 500 }
    );
  }
}
