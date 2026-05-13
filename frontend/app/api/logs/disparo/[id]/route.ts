import { NextResponse } from "next/server";
import { getDisparoLog } from "@/lib/server/logs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const result = await getDisparoLog(params.id);
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Log não encontrado" },
      { status: 404 }
    );
  }
}
