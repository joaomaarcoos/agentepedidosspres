import { NextResponse } from "next/server";
import { getAgentStatus, toggleAgent } from "@/lib/server/conexao";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { name: string } }
) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const result = await getAgentStatus(decodeURIComponent(params.name));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar status do agente" },
      { status: 500 }
    );
  }
}

export async function POST(
  request: Request,
  { params }: { params: { name: string } }
) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json();
    const enabled = Boolean(body.enabled);
    const result = await toggleAgent(decodeURIComponent(params.name), enabled);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao atualizar agente" },
      { status: 500 }
    );
  }
}
