import { NextResponse } from "next/server";
import { getQrCode } from "@/lib/server/conexao";
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
    const result = await getQrCode(decodeURIComponent(params.name));
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar QR code" },
      { status: 500 }
    );
  }
}
