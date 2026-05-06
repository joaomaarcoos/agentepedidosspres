import { NextResponse } from "next/server";
import { getRecorrenciaCliente } from "@/lib/server/recorrencia";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: { codCli: string } }
) {
  const codCli = Number(params.codCli);
  const { searchParams } = new URL(request.url);
  const dias = Number(searchParams.get("dias") ?? 180);

  if (!Number.isFinite(codCli)) {
    return NextResponse.json({ error: "Parâmetro codCli inválido" }, { status: 400 });
  }
  if (!Number.isFinite(dias) || dias < 1 || dias > 730) {
    return NextResponse.json({ error: "Parâmetro dias inválido" }, { status: 400 });
  }

  try {
    const result = await getRecorrenciaCliente(codCli, dias);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar recorrência do cliente" },
      { status: 500 }
    );
  }
}
