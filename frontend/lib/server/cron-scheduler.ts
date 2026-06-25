import fs from "fs";
import path from "path";

export interface CronSettings {
  enabled: boolean;
  interval_hours: number;
  dias?: number;
  rep_document?: string | null;
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

export function readCronSettings(): CronSettings {
  try {
    const p = getSettingsPath();
    if (fs.existsSync(p)) {
      return JSON.parse(fs.readFileSync(p, "utf-8")) as CronSettings;
    }
  } catch {}
  return { enabled: false, interval_hours: 24, dias: 2, rep_document: null, last_run: null, last_run_status: null };
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
    const repDocument = settings.rep_document || undefined;
    console.log(`[cron] Triggering scheduled sync (dias=${dias}, rep=${repDocument || "all"})...`);
    try {
      const { syncPedidos } = await import("@/lib/server/pedidos");
      const result = await syncPedidos(dias, "schedule", repDocument);
      const current = readCronSettings();
      writeCronSettings({
        ...current,
        last_run: new Date().toISOString(),
        last_run_status: result.status === "success" ? "success" : "error",
      });
      console.log("[cron] Sync finished:", result.message);
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
