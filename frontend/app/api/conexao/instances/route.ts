import { NextResponse } from "next/server";
import { filterInstancesForProfile, listInstances, createInstance, saveInstanceOwner } from "@/lib/server/conexao";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";
import { randomBytes } from "node:crypto";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const result = await listInstances();
    return NextResponse.json(await filterInstancesForProfile(result, auth.profile));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao listar instancias" },
      { status: 500 }
    );
  }
}

function buildWebhookUrl(request: Request, token: string): string {
  const appUrl = process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL;
  let webhookUrl: URL;

  if (appUrl) {
    const base = appUrl.startsWith("http") ? appUrl : `https://${appUrl}`;
    webhookUrl = new URL("/api/evolution/webhook", base);
  } else {
    const url = new URL(request.url);
    webhookUrl = new URL("/api/evolution/webhook", `${url.protocol}//${url.host}`);
  }

  if (token) {
    webhookUrl.searchParams.set("token", token);
  }

  return webhookUrl.toString();
}

function createWebhookToken(): string {
  return randomBytes(32).toString("base64url");
}

const DEFAULT_MSG_CALL = "No momento não consigo atender. Envie uma mensagem!";

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  try {
    const body = await request.json();
    const { name } = body as { name: string };
    if (!name || typeof name !== "string" || !name.trim()) {
      return NextResponse.json({ error: "Nome da instancia e obrigatorio" }, { status: 400 });
    }
    const webhookToken = process.env.EVOLUTION_WEBHOOK_SECRET || createWebhookToken();
    const result = await createInstance({
      name: name.trim(),
      webhookUrl: buildWebhookUrl(request, webhookToken),
      msgCall: DEFAULT_MSG_CALL,
    });
    const ownerSaved = await saveInstanceOwner(result.instanceName || name.trim(), auth.profile);
    if (auth.profile.role === "representante" && !ownerSaved) {
      return NextResponse.json(
        { error: "Instancia criada, mas nao foi possivel vincular a sua conta." },
        { status: 500 }
      );
    }
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao criar instancia" },
      { status: 500 }
    );
  }
}
