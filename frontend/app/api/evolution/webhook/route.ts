import { NextRequest, NextResponse } from "next/server";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createClient } from "@supabase/supabase-js";
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

function getPayloadInstance(payload: Record<string, unknown>) {
  return String(
    payload.instance ||
      payload.instanceName ||
      payload.sender ||
      (payload.data && typeof payload.data === "object" && "instance" in payload.data
        ? (payload.data as Record<string, unknown>).instance
        : "") ||
      ""
  ).trim();
}

async function isValidInstanceToken(instance: string, token: string) {
  if (!instance || !token) return false;

  const supabaseUrl = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY || "";
  if (!supabaseUrl || !supabaseKey) return false;

  const supabase = createClient(supabaseUrl, supabaseKey);
  const { data, error } = await supabase
    .from("system_settings")
    .select("value")
    .eq("key", `evolution_webhook_token__${instance}`)
    .limit(1)
    .maybeSingle();

  if (error || !data) return false;
  return data.value === token;
}

async function isAuthorizedWebhook(request: NextRequest, payload: Record<string, unknown>) {
  const token = getWebhookToken(request);
  const expectedToken = process.env.EVOLUTION_WEBHOOK_SECRET || process.env.EVOLUTION_API_KEY || "";

  if (expectedToken && token === expectedToken) {
    return true;
  }

  return isValidInstanceToken(getPayloadInstance(payload), token);
}

export async function POST(request: NextRequest) {
  let tempDir: string | null = null;

  try {
    const payload = await request.json();
    if (!(await isAuthorizedWebhook(request, payload))) {
      return NextResponse.json({ ok: false, error: "Nao autorizado." }, { status: 401 });
    }

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
