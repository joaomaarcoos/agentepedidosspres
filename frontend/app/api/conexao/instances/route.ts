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

function buildWebhookUrl(request: Request): string {
  const appUrl = process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL;
  if (appUrl) {
    const base = appUrl.startsWith("http") ? appUrl : `https://${appUrl}`;
    return `${base}/api/evolution/webhook`;
  }
  const url = new URL(request.url);
  return `${url.protocol}//${url.host}/api/evolution/webhook`;
}

const DEFAULT_MSG_CALL = "No momento não consigo atender. Envie uma mensagem!";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name } = body as { name: string };
    if (!name || typeof name !== "string" || !name.trim()) {
      return NextResponse.json({ error: "Nome da instancia e obrigatorio" }, { status: 400 });
    }
    const result = await createInstance({
      name: name.trim(),
      webhookUrl: buildWebhookUrl(request),
      msgCall: DEFAULT_MSG_CALL,
    });
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao criar instancia" },
      { status: 500 }
    );
  }
}
