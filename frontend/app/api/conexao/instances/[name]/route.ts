import { NextResponse } from "next/server";
import { deleteInstance } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function DELETE(
  _request: Request,
  { params }: { params: { name: string } }
) {
  try {
    const result = await deleteInstance(decodeURIComponent(params.name));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao apagar instancia" },
      { status: 500 }
    );
  }
}
