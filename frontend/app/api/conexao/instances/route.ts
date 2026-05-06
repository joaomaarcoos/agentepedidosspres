import { NextResponse } from "next/server";
import { listInstances, createInstance } from "@/lib/server/conexao";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await listInstances();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao listar instancias" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, webhookUrl, msgCall } = body as {
      name: string;
      webhookUrl?: string;
      msgCall?: string;
    };
    if (!name || typeof name !== "string" || !name.trim()) {
      return NextResponse.json({ error: "Nome da instancia e obrigatorio" }, { status: 400 });
    }
    const result = await createInstance({ name: name.trim(), webhookUrl, msgCall });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao criar instancia" },
      { status: 500 }
    );
  }
}
