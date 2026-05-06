import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "AgentePedidos Next.js API",
    version: "1.0.0",
    mode: "nextjs-fullstack",
  });
}
