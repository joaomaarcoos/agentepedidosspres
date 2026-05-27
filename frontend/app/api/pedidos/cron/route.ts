import { NextResponse } from "next/server";
import { readCronSettings, writeCronSettings } from "@/lib/server/cron-scheduler";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export async function GET() {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  return NextResponse.json(readCronSettings());
}

export async function POST(req: Request) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  const body = await req.json() as { enabled?: boolean; interval_hours?: number };
  const settings = readCronSettings();
  if (typeof body.enabled === "boolean") settings.enabled = body.enabled;
  if (typeof body.interval_hours === "number") settings.interval_hours = body.interval_hours;
  writeCronSettings(settings);
  return NextResponse.json(settings);
}
