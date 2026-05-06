import { NextResponse } from "next/server";
import { disconnectInstance } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _request: Request,
  { params }: { params: { name: string } }
) {
  try {
    const result = await disconnectInstance(decodeURIComponent(params.name));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao desconectar instancia" },
      { status: 500 }
    );
  }
}
