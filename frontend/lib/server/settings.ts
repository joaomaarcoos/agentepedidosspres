import { runPythonJson } from "@/lib/server/python";

type Envelope<T> = { ok: true; data: T } | { ok: false; error: string };

async function callSettings<T>(args: string[]) {
  const result = await runPythonJson<Envelope<T>>("execution/settings_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function getDisparoSettings() {
  return callSettings<{ disparo_recorrencia: boolean; disparo_ativacao: boolean }>(["get"]);
}

export function setDisparoSetting(
  key: "disparo_recorrencia_enabled" | "disparo_ativacao_enabled",
  value: boolean
) {
  return callSettings<{ key: string; value: boolean }>(["set", "--key", key, "--value", String(value)]);
}
