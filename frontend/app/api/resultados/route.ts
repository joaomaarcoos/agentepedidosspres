import { NextResponse } from "next/server";
import { listResultados } from "@/lib/server/resultados";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const VALID_TYPES = ["all", "recorrencia", "ativacao"];

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const targetType = (searchParams.get("target_type") ?? "all") as "all" | "recorrencia" | "ativacao";
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 50);

    if (!VALID_TYPES.includes(targetType)) {
      return NextResponse.json({ error: "Parâmetro target_type inválido" }, { status: 400 });
    }
    if (!Number.isFinite(page) || page < 1) {
      return NextResponse.json({ error: "Parâmetro page inválido" }, { status: 400 });
    }
    if (!Number.isFinite(pageSize) || pageSize < 1 || pageSize > 200) {
      return NextResponse.json({ error: "Parâmetro page_size inválido" }, { status: 400 });
    }

    const result = await listResultados({ targetType, page, pageSize });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro interno" },
      { status: 500 }
    );
  }
}
