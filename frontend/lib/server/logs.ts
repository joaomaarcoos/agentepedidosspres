import { runPythonJson } from "@/lib/server/python";
import type { DisparoLog, DisparoLogsOverview } from "@/lib/types";

type Envelope<T> = { ok: true; data: T } | { ok: false; error: string };

async function callLogs<T>(args: string[]) {
  const result = await runPythonJson<Envelope<T>>("execution/logs_cli.py", args);
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export function listDisparoLogs(params: {
  flow?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}) {
  const args = ["list"];
  if (params.flow) args.push("--flow", params.flow);
  if (params.status) args.push("--status", params.status);
  if (params.page !== undefined) args.push("--page", String(params.page));
  if (params.pageSize !== undefined) args.push("--page-size", String(params.pageSize));
  return callLogs<DisparoLogsOverview>(args);
}

export function getDisparoLog(id: string) {
  return callLogs<DisparoLog>(["detail", "--id", id]);
}
