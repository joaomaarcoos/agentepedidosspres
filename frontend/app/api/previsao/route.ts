import { NextResponse } from "next/server";
import { getPrevisao } from "@/lib/server/pedidos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const yearParam = searchParams.get("year");
    const codRepParam = searchParams.get("cod_rep");
    const periodCount = Number(searchParams.get("period_count") ?? 4);
    const limit = Number(searchParams.get("limit") ?? 10);

    if (!Number.isFinite(periodCount) || ![3, 4].includes(periodCount)) {
      return NextResponse.json({ error: "Parametro period_count invalido" }, { status: 400 });
    }
    if (!Number.isFinite(limit) || limit < 1 || limit > 50) {
      return NextResponse.json({ error: "Parametro limit invalido" }, { status: 400 });
    }

    const parsedYear = yearParam ? Number(yearParam) : undefined;
    if (parsedYear !== undefined && (!Number.isFinite(parsedYear) || parsedYear < 2000 || parsedYear > 2100)) {
      return NextResponse.json({ error: "Parametro year invalido" }, { status: 400 });
    }
    const requestedCodRep = codRepParam ? Number(codRepParam) : undefined;
    if (codRepParam && !Number.isFinite(requestedCodRep)) {
      return NextResponse.json({ error: "Parametro cod_rep invalido" }, { status: 400 });
    }
    if (auth.profile.role === "representante" && auth.profile.cod_rep == null) {
      return NextResponse.json({ error: "Representante sem cod_rep vinculado." }, { status: 403 });
    }
    const codRep = auth.profile.role === "representante" ? auth.profile.cod_rep ?? undefined : requestedCodRep;

    const result = await getPrevisao({ year: parsedYear, periodCount, limit, codRep });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao gerar previsao" },
      { status: 500 }
    );
  }
}
