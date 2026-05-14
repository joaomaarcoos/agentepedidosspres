import fs from "fs";
import path from "path";

export interface CronSettings {
  enabled: boolean;
  interval_hours: number;
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
  return { enabled: false, interval_hours: 1, last_run: null, last_run_status: null };
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

    console.log("[cron] Triggering scheduled sync (dias=1)...");
    try {
      const { runPythonJson } = await import("@/lib/server/python");
      type SyncResult = { status: string; message: string };
      const result = await runPythonJson<SyncResult>("execution/clic_vendas_cli.py", [
        "sync",
        "--dias",
        "1",
        "--triggered-by",
        "schedule",
      ]);
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
