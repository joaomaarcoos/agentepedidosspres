import { runPythonJson } from "@/lib/server/python";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import type { ApiAuthSuccess } from "@/lib/server/api-auth";
import type {
  AgentType,
  ConexaoStatus,
  CreateInstanceResult,
  EvolutionInstance,
  EvolutionInstancesResponse,
  InstanceActionResult,
  QrCodeResult,
} from "@/lib/types";

type Envelope<T> = { ok: true; data: T } | { ok: false; error: string };
type ApiProfile = ApiAuthSuccess["profile"];
type InstanceOwner = {
  user_id: string;
  role: string;
  cod_rep: number | null;
};

async function call<T>(args: string[]): Promise<T> {
  const result = await runPythonJson<Envelope<T>>("execution/conexao_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function getConexaoStatus() {
  return call<ConexaoStatus>(["status"]);
}

export async function listInstances() {
  const result = await call<EvolutionInstancesResponse>(["list"]);
  const client = settingsClient();
  if (!client || !(result.instances ?? []).length) return result;
  const keys = result.instances.map((instance) => agentConfigKey(instance.instanceName));
  const { data } = await client.from("system_settings").select("key,value").in("key", keys);
  const configs = new Map(
    (data ?? []).map((row) => [String(row.key), row.value as Record<string, unknown>])
  );
  return {
    ...result,
    instances: result.instances.map((instance) => {
      const config = configs.get(agentConfigKey(instance.instanceName));
      return {
        ...instance,
        agent_type: (config?.agent_type === "secretary" ? "secretary" : "sales") as AgentType,
        agent_enabled: config?.agent_enabled !== false,
      };
    }),
  };
}

function ownerKey(name: string) {
  return `evolution_instance_owner__${name}`;
}

function agentConfigKey(name: string) {
  return `agent_instance_config__${name}`;
}

function settingsClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) return null;
  return createSupabaseClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

export async function saveInstanceOwner(name: string, profile: ApiProfile) {
  const client = settingsClient();
  if (!client || !name) return false;

  const { error } = await client.from("system_settings").upsert({
    key: ownerKey(name),
    value: {
      user_id: profile.id,
      role: profile.role,
      cod_rep: profile.cod_rep,
    },
    updated_at: new Date().toISOString(),
  });

  return !error;
}

export async function saveInstanceAgentConfig(
  name: string,
  agentType: AgentType,
  profile: ApiProfile
) {
  const client = settingsClient();
  if (!client || !name) return false;
  const now = new Date().toISOString();
  const { error } = await client.from("system_settings").upsert({
    key: agentConfigKey(name),
    value: {
      instance_name: name,
      agent_type: agentType,
      agent_enabled: true,
      created_by: profile.id,
      created_at: now,
    },
    updated_at: now,
  });
  return !error;
}

async function loadInstanceOwner(name: string): Promise<InstanceOwner | null> {
  const client = settingsClient();
  if (!client || !name) return null;

  const { data } = await client
    .from("system_settings")
    .select("value")
    .eq("key", ownerKey(name))
    .limit(1)
    .maybeSingle();

  const value = data?.value as Partial<InstanceOwner> | null | undefined;
  if (!value?.user_id) return null;
  return {
    user_id: String(value.user_id),
    role: String(value.role || ""),
    cod_rep: typeof value.cod_rep === "number" ? value.cod_rep : null,
  };
}

export async function canManageInstance(name: string, profile: ApiProfile) {
  if (profile.role !== "representante") return true;
  const owner = await loadInstanceOwner(name);
  return owner?.user_id === profile.id;
}

export async function filterInstancesForProfile(
  result: EvolutionInstancesResponse,
  profile: ApiProfile
): Promise<EvolutionInstancesResponse> {
  if (profile.role !== "representante") return result;

  const instances: EvolutionInstance[] = [];
  for (const instance of result.instances ?? []) {
    if (await canManageInstance(instance.instanceName, profile)) {
      instances.push(instance);
    }
  }

  return {
    ...result,
    instances,
    total: instances.length,
  };
}

export function createInstance(params: {
  name: string;
  webhookUrl?: string;
  msgCall?: string;
}) {
  const args = ["create", "--name", params.name];
  if (params.webhookUrl) args.push("--webhook-url", params.webhookUrl);
  if (params.msgCall) args.push("--msg-call", params.msgCall);
  return call<CreateInstanceResult>(args);
}

export function getQrCode(name: string) {
  return call<QrCodeResult>(["qrcode", "--name", name]);
}

export function deleteInstance(name: string) {
  return call<InstanceActionResult>(["delete", "--name", name]);
}

export function disconnectInstance(name: string) {
  return call<InstanceActionResult>(["disconnect", "--name", name]);
}

export function restartInstance(name: string) {
  return call<InstanceActionResult>(["restart", "--name", name]);
}

export function getAgentStatus(name: string) {
  return call<{ instanceName: string; agent_enabled: boolean }>(["agent-status", "--name", name]);
}

export function toggleAgent(name: string, enabled: boolean) {
  return call<{ instanceName: string; agent_enabled: boolean }>(
    ["agent-toggle", "--name", name, "--enabled", enabled ? "true" : "false"]
  );
}
