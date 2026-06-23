import { NextResponse } from "next/server";
import { getSecretaryConversation } from "@/lib/server/secretary-conversations";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Params = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, { params }: Params) {
  const auth = await requireApiRole(API_ROLES.MASTER);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const { id } = await params;
    const result = await getSecretaryConversation(id);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar conversa da secretaria" },
      { status: 500 }
    );
  }
}
