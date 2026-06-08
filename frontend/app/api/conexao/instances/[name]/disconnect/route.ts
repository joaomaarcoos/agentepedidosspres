import { NextResponse } from "next/server";
import { canManageInstance, disconnectInstance } from "@/lib/server/conexao";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  _request: Request,
  { params }: { params: { name: string } }
) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const name = decodeURIComponent(params.name);
    if (!(await canManageInstance(name, auth.profile))) {
      return NextResponse.json({ error: "Sem permissao para esta instancia." }, { status: 403 });
    }
    const result = await disconnectInstance(name);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao desconectar instancia" },
      { status: 500 }
    );
  }
}
