import { NextResponse } from "next/server";
import { readCronSettings, writeCronSettings } from "@/lib/server/cron-scheduler";

export async function GET() {
  return NextResponse.json(readCronSettings());
}

export async function POST(req: Request) {
  const body = await req.json() as { enabled?: boolean; interval_hours?: number };
  const settings = readCronSettings();
  if (typeof body.enabled === "boolean") settings.enabled = body.enabled;
  if (typeof body.interval_hours === "number") settings.interval_hours = body.interval_hours;
  writeCronSettings(settings);
  return NextResponse.json(settings);
}
