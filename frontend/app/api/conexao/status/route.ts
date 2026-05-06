import { NextResponse } from "next/server";
import { getConexaoStatus } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await getConexaoStatus();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao verificar conexao" },
      { status: 500 }
    );
  }
}
