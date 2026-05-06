import { runPythonJson } from "@/lib/server/python";
import type {
  ConexaoStatus,
  CreateInstanceResult,
  EvolutionInstancesResponse,
  InstanceActionResult,
  QrCodeResult,
} from "@/lib/types";

type Envelope<T> = { ok: true; data: T } | { ok: false; error: string };

async function call<T>(args: string[]): Promise<T> {
  const result = await runPythonJson<Envelope<T>>("execution/conexao_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function getConexaoStatus() {
  return call<ConexaoStatus>(["status"]);
}

export function listInstances() {
  return call<EvolutionInstancesResponse>(["list"]);
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
