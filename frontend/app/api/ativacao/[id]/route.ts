import { NextResponse } from "next/server";
import { getAtivacaoTarget } from "@/lib/server/ativacao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const result = await getAtivacaoTarget({ id: params.id });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Registro não encontrado" },
      { status: 500 }
    );
  }
}
