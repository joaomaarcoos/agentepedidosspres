import { NextResponse } from "next/server";
import { listClientes, syncClientes } from "@/lib/server/clientes";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get("query") || undefined;
    const codRepParam = searchParams.get("cod_rep");
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 50);

    if (!Number.isFinite(page) || page < 1) {
      return NextResponse.json({ error: "Parâmetro page inválido" }, { status: 400 });
    }
    if (!Number.isFinite(pageSize) || pageSize < 1 || pageSize > 200) {
      return NextResponse.json({ error: "Parâmetro page_size inválido" }, { status: 400 });
    }
    const requestedCodRep = codRepParam ? Number(codRepParam) : undefined;
    if (codRepParam && !Number.isFinite(requestedCodRep)) {
      return NextResponse.json({ error: "Parametro cod_rep invalido" }, { status: 400 });
    }
    if (auth.profile.role === "representante" && auth.profile.cod_rep == null) {
      return NextResponse.json({ error: "Representante sem cod_rep vinculado." }, { status: 403 });
    }
    const codRep = auth.profile.role === "representante" ? auth.profile.cod_rep ?? undefined : requestedCodRep;

    const result = await listClientes({ query, page, pageSize, codRep });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao listar clientes" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

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
