import { runPythonJson } from "@/lib/server/python";
import type { SecretaryDashboard, SecretaryMetrics } from "@/lib/types";

type Envelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function getSecretaryMetrics(dateFrom?: string, dateTo?: string) {
  const args = ["metrics"];
  if (dateFrom) args.push("--date-from", dateFrom);
  if (dateTo) args.push("--date-to", dateTo);
  const result = await runPythonJson<Envelope<SecretaryMetrics>>(
    "execution/secretary_cli.py",
    args
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export async function getSecretaryDashboard(params: {
  dateFrom?: string;
  dateTo?: string;
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
  codRep?: number;
}) {
  const args = ["dashboard"];
  if (params.dateFrom) args.push("--date-from", params.dateFrom);
  if (params.dateTo) args.push("--date-to", params.dateTo);
  if (params.status) args.push("--status", params.status);
  if (params.search) args.push("--search", params.search);
  args.push("--page", String(params.page || 1));
  args.push("--page-size", String(params.pageSize || 25));
  if (params.codRep !== undefined) args.push("--cod-rep", String(params.codRep));
  const result = await runPythonJson<Envelope<SecretaryDashboard>>(
    "execution/secretary_cli.py",
    args
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}
