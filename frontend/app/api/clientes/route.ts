import { NextResponse } from "next/server";
import { listClientes, syncClientes } from "@/lib/server/clientes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get("query") || undefined;
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 50);

    if (!Number.isFinite(page) || page < 1) {
      return NextResponse.json({ error: "Parâmetro page inválido" }, { status: 400 });
    }
    if (!Number.isFinite(pageSize) || pageSize < 1 || pageSize > 200) {
      return NextResponse.json({ error: "Parâmetro page_size inválido" }, { status: 400 });
    }

    const result = await listClientes({ query, page, pageSize });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao listar clientes" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as { query?: string };
    const result = await syncClientes(body.query);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao sincronizar clientes" },
      { status: 500 }
    );
  }
}
