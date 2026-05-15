import fs from "fs";
import path from "path";

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
