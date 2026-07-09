import { runPythonJson } from "@/lib/server/python";
import type { RequisitionLog, RequisitionLogsOverview } from "@/lib/types";

type Envelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function listRequisitionLogs(params: {
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}) {
  const args = ["list"];
  if (params.status) args.push("--status", params.status);
  if (params.dateFrom) args.push("--date-from", params.dateFrom);
  if (params.dateTo) args.push("--date-to", params.dateTo);
  if (params.search) args.push("--search", params.search);
  args.push("--page", String(params.page || 1));
  args.push("--page-size", String(params.pageSize || 30));

  const result = await runPythonJson<Envelope<RequisitionLogsOverview>>(
    "execution/requisition_logs_cli.py",
    args
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export async function getRequisitionLog(id: string) {
  const result = await runPythonJson<Envelope<RequisitionLog>>(
    "execution/requisition_logs_cli.py",
    ["detail", id]
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}
