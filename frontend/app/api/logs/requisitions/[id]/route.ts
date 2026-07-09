import { NextResponse } from "next/server";
import { getRequisitionLog } from "@/lib/server/requisition-logs";
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
    const result = await getRequisitionLog(id);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar Requisition Log" },
      { status: 500 }
    );
  }
}
