import { NextResponse } from "next/server";
import { restartInstance } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _request: Request,
  { params }: { params: { name: string } }
) {
  try {
    const result = await restartInstance(decodeURIComponent(params.name));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao reiniciar instancia" },
      { status: 500 }
    );
  }
}
