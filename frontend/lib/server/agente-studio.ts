import fs from "fs";
import path from "path";
import { createClient } from "@supabase/supabase-js";

const PROMPTS_DIR = path.join(process.cwd(), "..", "prompts", "marcela");

const KNOWN_ORDER = [
  "system",
  "personality",
  "business_rules",
  "sales_strategy",
  "examples",
  "tools",
];

const LABELS: Record<string, { label: string; description: string }> = {
  system:          { label: "Identidade",          description: "Quem é a Marcela e seu papel principal" },
  personality:     { label: "Personalidade",        description: "Tom de voz e comportamentos obrigatórios" },
  business_rules:  { label: "Regras de Negócio",    description: "O que pode e não pode fazer" },
  sales_strategy:  { label: "Estratégia de Vendas", description: "Como abordar recorrência e ativação" },
  examples:        { label: "Exemplos",             description: "Conversas modelo para referência" },
  tools:           { label: "Capacidades",          description: "Ferramentas e informações disponíveis" },
};

export interface PromptFile {
  slug: string;
  filename: string;
  label: string;
  description: string;
  content: string;
  lines: number;
  core: boolean;
  updatedAt: string;
}

function slugFromFilename(filename: string): string {
  return filename.replace(/\.md$/, "");
}

function ensureDir() {
  if (!fs.existsSync(PROMPTS_DIR)) {
    fs.mkdirSync(PROMPTS_DIR, { recursive: true });
  }
}

export function listPrompts(): PromptFile[] {
  ensureDir();
  const files = fs.readdirSync(PROMPTS_DIR).filter((f) => f.endsWith(".md"));
  const known = KNOWN_ORDER.filter((s) => files.includes(`${s}.md`));
  const extras = files
    .map((f) => slugFromFilename(f))
    .filter((s) => !KNOWN_ORDER.includes(s))
    .sort();
  const slugs = [...known, ...extras];

  return slugs.map((slug) => {
    const filepath = path.join(PROMPTS_DIR, `${slug}.md`);
    const content = fs.readFileSync(filepath, "utf-8");
    const stat = fs.statSync(filepath);
    const meta = LABELS[slug];
    return {
      slug,
      filename: `${slug}.md`,
      label: meta?.label ?? slug,
      description: meta?.description ?? "",
      content,
      lines: content.split("\n").length,
      core: KNOWN_ORDER.includes(slug),
      updatedAt: stat.mtime.toISOString(),
    };
  });
}

export function getPrompt(slug: string): PromptFile | null {
  ensureDir();
  const filepath = path.join(PROMPTS_DIR, `${slug}.md`);
  if (!fs.existsSync(filepath)) return null;
  const content = fs.readFileSync(filepath, "utf-8");
  const stat = fs.statSync(filepath);
  const meta = LABELS[slug];
  return {
    slug,
    filename: `${slug}.md`,
    label: meta?.label ?? slug,
    description: meta?.description ?? "",
    content,
    lines: content.split("\n").length,
    core: KNOWN_ORDER.includes(slug),
    updatedAt: stat.mtime.toISOString(),
  };
}

export function savePrompt(slug: string, content: string): PromptFile {
  ensureDir();
  const safe = slug.replace(/[^a-z0-9_-]/gi, "_").toLowerCase();
  const filepath = path.join(PROMPTS_DIR, `${safe}.md`);
  fs.writeFileSync(filepath, content, "utf-8");
  return getPrompt(safe)!;
}

export function deletePrompt(slug: string): void {
  const filepath = path.join(PROMPTS_DIR, `${slug}.md`);
  if (!fs.existsSync(filepath)) throw new Error(`Prompt "${slug}" não encontrado`);
  if (KNOWN_ORDER.includes(slug)) throw new Error(`Prompt "${slug}" é essencial e não pode ser removido`);
  fs.unlinkSync(filepath);
}

export type AgentRuntimeSettings = {
  message_buffer_seconds: number;
};

const DEFAULT_RUNTIME_SETTINGS: AgentRuntimeSettings = {
  message_buffer_seconds: 5,
};

function settingsClient() {
  const url = (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
  const key = (
    process.env.SUPABASE_SERVICE_ROLE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
    ""
  ).trim();
  if (!url || !key) return null;
  return createClient(url, key);
}

function settingsFallbackPath() {
  return path.join(process.cwd(), "..", ".tmp", "data", "agent_runtime_settings.json");
}

function normalizeRuntimeSettings(raw: Partial<AgentRuntimeSettings>): AgentRuntimeSettings {
  const buffer = Number(raw.message_buffer_seconds);
  return {
    message_buffer_seconds: Number.isFinite(buffer)
      ? Math.max(0, Math.min(30, buffer))
      : DEFAULT_RUNTIME_SETTINGS.message_buffer_seconds,
  };
}

export async function getAgentRuntimeSettings(): Promise<AgentRuntimeSettings> {
  const client = settingsClient();
  if (client) {
    const { data } = await client
      .from("system_settings")
      .select("key,value")
      .eq("key", "ai_message_buffer_seconds")
      .limit(1);
    const value = data?.[0]?.value;
    return normalizeRuntimeSettings({
      message_buffer_seconds: value ?? DEFAULT_RUNTIME_SETTINGS.message_buffer_seconds,
    });
  }

  try {
    const file = settingsFallbackPath();
    if (fs.existsSync(file)) {
      return normalizeRuntimeSettings(JSON.parse(fs.readFileSync(file, "utf-8")));
    }
  } catch {
    return DEFAULT_RUNTIME_SETTINGS;
  }
  return DEFAULT_RUNTIME_SETTINGS;
}

export async function saveAgentRuntimeSettings(
  settings: Partial<AgentRuntimeSettings>
): Promise<AgentRuntimeSettings> {
  const normalized = normalizeRuntimeSettings(settings);
  const client = settingsClient();
  if (client) {
    await client
      .from("system_settings")
      .upsert({
        key: "ai_message_buffer_seconds",
        value: normalized.message_buffer_seconds,
        updated_at: new Date().toISOString(),
      });
    return normalized;
  }

  const file = settingsFallbackPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(normalized, null, 2), "utf-8");
  return normalized;
}
