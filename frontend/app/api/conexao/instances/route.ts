import { NextResponse } from "next/server";
import {
  filterInstancesForProfile,
  listInstances,
  createInstance,
  saveInstanceAgentConfig,
  saveInstanceOwner,
} from "@/lib/server/conexao";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";
import { randomBytes } from "node:crypto";
import type { AgentType } from "@/lib/types";

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
    const { name, agent_type } = body as { name: string; agent_type: AgentType };
    if (!name || typeof name !== "string" || !name.trim()) {
      return NextResponse.json({ error: "Nome da instancia e obrigatorio" }, { status: 400 });
    }
    if (!["sales", "secretary"].includes(agent_type)) {
      return NextResponse.json({ error: "Agente conectado e obrigatorio" }, { status: 400 });
    }
    if (agent_type === "secretary" && !API_ROLES.GESTOR_UP.includes(auth.profile.role)) {
      return NextResponse.json(
        { error: "Somente perfis administrativos podem criar a Marcela Secretaria." },
        { status: 403 }
      );
    }
    const webhookToken = process.env.EVOLUTION_WEBHOOK_SECRET || createWebhookToken();
    const result = await createInstance({
      name: name.trim(),
      webhookUrl: buildWebhookUrl(request, webhookToken),
      msgCall: DEFAULT_MSG_CALL,
    });
    const ownerSaved = await saveInstanceOwner(result.instanceName || name.trim(), auth.profile);
    const configSaved = await saveInstanceAgentConfig(
      result.instanceName || name.trim(),
      agent_type,
      auth.profile
    );
    if (auth.profile.role === "representante" && !ownerSaved) {
      return NextResponse.json(
        { error: "Instancia criada, mas nao foi possivel vincular a sua conta." },
        { status: 500 }
      );
    }
    if (!configSaved) {
      return NextResponse.json(
        { error: "Instancia criada, mas nao foi possivel salvar o agente conectado." },
        { status: 500 }
      );
    }
    return NextResponse.json({ ...result, agent_type, agent_enabled: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao criar instancia" },
      { status: 500 }
    );
  }
}
