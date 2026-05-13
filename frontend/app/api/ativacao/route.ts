import { NextResponse } from "next/server";
import { listAtivacao } from "@/lib/server/ativacao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const VALID_STATUSES = new Set([
  "activation_candidate",
  "activation_approved",
  "activation_rejected",
  "dispatched",
]);

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const statusParam = searchParams.get("status") ?? "";
    const page = Math.max(1, Number(searchParams.get("page") ?? "1"));
    const pageSize = Math.min(200, Math.max(1, Number(searchParams.get("page_size") ?? "50")));

    const status = VALID_STATUSES.has(statusParam) ? statusParam : undefined;

    const result = await listAtivacao({ status, page, pageSize });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao listar ativação" },
      { status: 500 }
    );
  }
}
