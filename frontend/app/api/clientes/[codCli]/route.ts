import { NextResponse } from "next/server";
import { getCliente } from "@/lib/server/clientes";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { codCli: string } }
) {
  const codCli = Number(params.codCli);
  if (!Number.isFinite(codCli)) {
    return NextResponse.json({ error: "Parâmetro codCli inválido" }, { status: 400 });
  }

  try {
    const result = await getCliente(codCli);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar cliente" },
      { status: 500 }
    );
  }
}
