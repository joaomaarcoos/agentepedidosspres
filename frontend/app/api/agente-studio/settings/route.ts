import { NextResponse } from "next/server";
import {
  getAgentRuntimeSettings,
  saveAgentRuntimeSettings,
} from "@/lib/server/agente-studio";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    return NextResponse.json(await getAgentRuntimeSettings());
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar configuracoes" },
      { status: 500 }
    );
  }
}

export async function PATCH(request: Request) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = (await request.json()) as { message_buffer_seconds?: number };
    return NextResponse.json(await saveAgentRuntimeSettings(body));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao salvar configuracoes" },
      { status: 500 }
    );
  }
}
