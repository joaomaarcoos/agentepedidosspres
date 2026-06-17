import { NextResponse } from "next/server";
import { syncPedidos } from "@/lib/server/pedidos";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json();
    const dias = Number(body?.dias ?? 30);
    const triggeredBy = String(body?.triggered_by ?? "manual");
    const repDocument = typeof body?.rep_document === "string" ? body.rep_document.replace(/\D/g, "") : undefined;

    if (!Number.isFinite(dias) || dias < 1 || dias > 365) {
      return NextResponse.json({ error: "Parâmetro dias inválido" }, { status: 400 });
    }

    if (repDocument && repDocument.length < 5) {
      return NextResponse.json({ error: "Documento do representante invalido" }, { status: 400 });
    }

    const result = await syncPedidos(dias, triggeredBy, repDocument);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno ao sincronizar" },
      { status: 500 }
    );
  }
}
