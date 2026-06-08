import { NextResponse } from "next/server";
import { listProdutos } from "@/lib/server/produtos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { searchParams } = new URL(request.url);
    const filial = searchParams.get("filial") || undefined;
    const busca = searchParams.get("busca") || undefined;

    const result = await listProdutos({ filial, busca });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar produtos" },
      { status: 500 }
    );
  }
}
