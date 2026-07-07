import fs from "fs";
import path from "path";

export interface CronSettings {
  enabled: boolean;
  interval_hours: number;
  dias?: number;
  rep_document?: string | null;
  rep_documents?: string[];
  last_run: string | null;
  last_run_status: "success" | "error" | null;
}

function getSettingsPath(): string {
  const cwd = process.cwd();
  const root = fs.existsSync(path.join(cwd, "execution"))
    ? cwd
    : path.resolve(cwd, "..");
  return path.join(root, ".tmp", "cron_settings.json");
}

function parseRepDocuments(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item || "").replace(/\D/g, ""))
      .filter((item) => item.length >= 5);
  }

  return String(value || "")
    .split(/[,\s;]+/)
    .map((item) => item.replace(/\D/g, ""))
    .filter((item) => item.length >= 5);
}

function defaultRepDocuments(): string[] {
  return parseRepDocuments(process.env.CLIC_VENDAS_REP_DOCUMENTS || process.env.CLIC_VENDAS_REP_DOCUMENT);
}

function normalizeSettings(settings: Partial<CronSettings>): CronSettings {
  const repDocuments = parseRepDocuments(settings.rep_documents);
  const fallbackDocuments = repDocuments.length > 0
    ? repDocuments
    : defaultRepDocuments();
  const legacyDocument = String(settings.rep_document || "").replace(/\D/g, "");
  const documents = fallbackDocuments.length > 0
    ? fallbackDocuments
    : legacyDocument
      ? [legacyDocument]
      : [];

  return {
    enabled: Boolean(settings.enabled),
    interval_hours: Number(settings.interval_hours || 24),
    dias: Number(settings.dias || 2),
    rep_document: documents[0] || null,
    rep_documents: documents,
    last_run: settings.last_run || null,
    last_run_status: settings.last_run_status || null,
  };
}

export function readCronSettings(): CronSettings {
  try {
    const p = getSettingsPath();
    if (fs.existsSync(p)) {
      const raw = fs.readFileSync(p, "utf-8").replace(/^\uFEFF/, "");
      return normalizeSettings(JSON.parse(raw) as Partial<CronSettings>);
    }
  } catch {}
  return normalizeSettings({ enabled: false, interval_hours: 24, dias: 2, last_run: null, last_run_status: null });
}

export function writeCronSettings(s: CronSettings): void {
  try {
    const p = getSettingsPath();
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, JSON.stringify(s, null, 2));
  } catch (e) {
    console.error("[cron] Failed to write settings:", e);
  }
}

let schedulerStarted = false;

export function startCronScheduler(): void {
  if (schedulerStarted) return;
  schedulerStarted = true;

  console.log("[cron] Scheduler initialized — checks every 60s");

  setInterval(async () => {
    const settings = readCronSettings();
    if (!settings.enabled) return;

    const now = new Date();
    if (settings.last_run) {
      const hoursSince =
        (now.getTime() - new Date(settings.last_run).getTime()) / 3_600_000;
      if (hoursSince < settings.interval_hours) return;
    }

    const dias = Math.max(1, Number(settings.dias || 2));
    const repDocuments = parseRepDocuments(settings.rep_documents);
    console.log(`[cron] Triggering scheduled sync (dias=${dias}, reps=${repDocuments.length || "all"})...`);
    try {
      const { syncPedidos } = await import("@/lib/server/pedidos");
      const results = repDocuments.length > 0
        ? await Promise.all(repDocuments.map((repDocument) => syncPedidos(dias, "schedule", repDocument)))
        : [await syncPedidos(dias, "schedule")];
      const current = readCronSettings();
      writeCronSettings({
        ...current,
        last_run: new Date().toISOString(),
        last_run_status: results.every((result) => result.status === "success") ? "success" : "error",
      });
      console.log("[cron] Sync finished:", results.map((result) => result.message).join(" | "));
    } catch (e) {
      const current = readCronSettings();
      writeCronSettings({
        ...current,
        last_run: new Date().toISOString(),
        last_run_status: "error",
      });
      console.error("[cron] Sync error:", e);
    }
  }, 60_000);
}
