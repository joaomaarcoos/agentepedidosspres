import { runPythonJson } from "@/lib/server/python";
import type { SecretaryConversationDetail, SecretaryConversationsOverview } from "@/lib/types";

type Envelope<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function listSecretaryConversations(params: {
  search?: string;
  page?: number;
  pageSize?: number;
}) {
  const args = ["list"];
  if (params.search) args.push("--search", params.search);
  args.push("--page", String(params.page || 1));
  args.push("--page-size", String(params.pageSize || 30));

  const result = await runPythonJson<Envelope<SecretaryConversationsOverview>>(
    "execution/secretary_conversations_cli.py",
    args
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}

export async function getSecretaryConversation(id: string) {
  const result = await runPythonJson<Envelope<SecretaryConversationDetail>>(
    "execution/secretary_conversations_cli.py",
    ["detail", id]
  );
  if (!result.ok) throw new Error(result.error);
  return result.data;
}
