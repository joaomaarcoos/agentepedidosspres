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

  const body = await req.json() as {
    enabled?: boolean;
    interval_hours?: number;
    dias?: number;
    rep_document?: string | null;
    rep_documents?: string[] | null;
  };
  const settings = readCronSettings();
  if (typeof body.enabled === "boolean") settings.enabled = body.enabled;
  if (typeof body.interval_hours === "number") {
    settings.interval_hours = body.interval_hours;
  } else if (body.enabled === true && settings.interval_hours < 24) {
    settings.interval_hours = 24;
  }
  if (typeof body.dias === "number") {
    settings.dias = Math.max(1, Math.floor(body.dias));
  }
  if (body.rep_document !== undefined) {
    const cleaned = String(body.rep_document || "").replace(/\D/g, "");
    settings.rep_document = cleaned || null;
    settings.rep_documents = cleaned ? [cleaned] : [];
  }
  if (body.rep_documents !== undefined) {
    const documents = Array.isArray(body.rep_documents)
      ? body.rep_documents
          .map((item) => String(item || "").replace(/\D/g, ""))
          .filter((item) => item.length >= 5)
      : [];
    settings.rep_documents = documents;
    settings.rep_document = documents[0] || null;
  }
  writeCronSettings(settings);
  return NextResponse.json(settings);
}
