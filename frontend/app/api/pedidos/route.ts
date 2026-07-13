import { NextResponse } from "next/server";
import { listPedidos } from "@/lib/server/pedidos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const codCliParam = searchParams.get("cod_cli");
    const codRepParam = searchParams.get("cod_rep");
    const origin = searchParams.get("origin") || "all";
    const dias = Number(searchParams.get("dias") ?? 0);
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 50);

    if (!Number.isFinite(dias) || dias < 0 || dias > 3650) {
      return NextResponse.json({ error: "Parametro dias invalido" }, { status: 400 });
    }
    if (!Number.isFinite(page) || page < 1) {
      return NextResponse.json({ error: "Parametro page invalido" }, { status: 400 });
    }
    if (!Number.isFinite(pageSize) || pageSize < 1 || pageSize > 200) {
      return NextResponse.json({ error: "Parametro page_size invalido" }, { status: 400 });
    }
    if (!["all", "ia_secretaria"].includes(origin)) {
      return NextResponse.json({ error: "Parametro origin invalido" }, { status: 400 });
    }

    const codCli = codCliParam ? Number(codCliParam) : undefined;
    if (codCliParam && !Number.isFinite(codCli)) {
      return NextResponse.json({ error: "Parametro cod_cli invalido" }, { status: 400 });
    }
    const requestedCodRep = codRepParam ? Number(codRepParam) : undefined;
    if (codRepParam && !Number.isFinite(requestedCodRep)) {
      return NextResponse.json({ error: "Parametro cod_rep invalido" }, { status: 400 });
    }
    if (auth.profile.role === "representante" && auth.profile.cod_rep == null) {
      return NextResponse.json({ error: "Representante sem cod_rep vinculado." }, { status: 403 });
    }
    const codRep = auth.profile.role === "representante" ? auth.profile.cod_rep ?? undefined : requestedCodRep;

    const result = await listPedidos({ codCli, codRep, dias, page, pageSize, origin });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao buscar pedidos" },
      { status: 500 }
    );
  }
}
