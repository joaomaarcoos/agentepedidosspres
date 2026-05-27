import { NextRequest, NextResponse } from "next/server";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { runPythonJson } from "@/lib/server/python";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PythonEnvelope<T> = {
  ok: boolean;
  data?: T;
  error?: string;
};

function getWebhookToken(request: NextRequest) {
  const auth = request.headers.get("authorization") || "";
  if (auth.toLowerCase().startsWith("bearer ")) {
    return auth.slice(7).trim();
  }

  return request.headers.get("x-webhook-secret") || request.nextUrl.searchParams.get("token") || "";
}

export async function POST(request: NextRequest) {
  let tempDir: string | null = null;

  try {
    const expectedToken = process.env.EVOLUTION_WEBHOOK_SECRET ?? process.env.EVOLUTION_API_KEY;
    if (!expectedToken) {
      return NextResponse.json(
        { ok: false, error: "EVOLUTION_WEBHOOK_SECRET ou EVOLUTION_API_KEY nao configurado." },
        { status: 503 }
      );
    }

    if (getWebhookToken(request) !== expectedToken) {
      return NextResponse.json({ ok: false, error: "Nao autorizado." }, { status: 401 });
    }

    const payload = await request.json();
    tempDir = await mkdtemp(path.join(tmpdir(), "agente-pedidos-webhook-"));
    const payloadFile = path.join(tempDir, "payload.json");
    await writeFile(payloadFile, JSON.stringify(payload), "utf-8");

    const result = await runPythonJson<PythonEnvelope<Record<string, unknown>>>(
      "execution/evolution_webhook.py",
      ["--payload-file", payloadFile],
      { timeoutMs: 90_000 }
    );

    if (!result.ok) {
      return NextResponse.json({ ok: false, error: result.error }, { status: 500 });
    }

    return NextResponse.json({ ok: true, data: result.data });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "Erro no webhook" },
      { status: 500 }
    );
  } finally {
    if (tempDir) {
      await rm(tempDir, { recursive: true, force: true }).catch(() => undefined);
    }
  }
}
