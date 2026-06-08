import { NextResponse } from "next/server";
import { getCliente } from "@/lib/server/clientes";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: { codCli: string } }
) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  const codCli = Number(params.codCli);
  if (!Number.isFinite(codCli)) {
    return NextResponse.json({ error: "Parâmetro codCli inválido" }, { status: 400 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const codRepParam = searchParams.get("cod_rep");
    const requestedCodRep = codRepParam ? Number(codRepParam) : undefined;
    if (codRepParam && !Number.isFinite(requestedCodRep)) {
      return NextResponse.json({ error: "Parametro cod_rep invalido" }, { status: 400 });
    }
    if (auth.profile.role === "representante" && auth.profile.cod_rep == null) {
      return NextResponse.json({ error: "Representante sem cod_rep vinculado." }, { status: 403 });
    }
    const codRep = auth.profile.role === "representante" ? auth.profile.cod_rep ?? undefined : requestedCodRep;
    const result = await getCliente(codCli, codRep);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar cliente" },
      { status: 500 }
    );
  }
}
