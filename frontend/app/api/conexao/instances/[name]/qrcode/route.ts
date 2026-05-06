import { NextResponse } from "next/server";
import { getQrCode } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { name: string } }
) {
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
