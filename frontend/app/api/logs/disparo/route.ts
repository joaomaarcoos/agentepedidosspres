import { NextResponse } from "next/server";
import { listDisparoLogs } from "@/lib/server/logs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const flow = searchParams.get("flow") || undefined;
    const status = searchParams.get("status") || undefined;
    const page = Number(searchParams.get("page") ?? 1);
    const pageSize = Number(searchParams.get("page_size") ?? 30);

    const result = await listDisparoLogs({ flow, status, page, pageSize });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar logs" },
      { status: 500 }
    );
  }
}
