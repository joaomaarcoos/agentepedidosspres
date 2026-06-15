import { NextResponse } from "next/server";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";
import { listInstances } from "@/lib/server/conexao";
import { getSecretaryDashboard } from "@/lib/server/secretaria";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;
  if (auth.profile.role === "representante" && auth.profile.cod_rep == null) {
    return NextResponse.json({ error: "Representante sem cod_rep vinculado." }, { status: 403 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const canViewResults = auth.profile.role !== "representante";
    const [dashboard, instances] = await Promise.all([
      getSecretaryDashboard({
        dateFrom: searchParams.get("date_from") || undefined,
        dateTo: searchParams.get("date_to") || undefined,
        status: searchParams.get("status") || undefined,
        search: searchParams.get("search") || undefined,
        page: Number(searchParams.get("page") || 1),
        pageSize: Number(searchParams.get("page_size") || 25),
        codRep: auth.profile.role === "representante" ? auth.profile.cod_rep ?? undefined : undefined,
      }),
      canViewResults
        ? listInstances().catch(() => ({
            instances: [],
            total: 0,
            api_online: false,
            api_url: null,
            checked_at: new Date().toISOString(),
            env: {},
          }))
        : Promise.resolve({
            instances: [],
            total: 0,
            api_online: false,
            api_url: null,
            checked_at: new Date().toISOString(),
            env: {},
          }),
    ]);

    const safeMetrics = canViewResults
      ? dashboard.metrics
      : {
          ...dashboard.metrics,
          total_value: 0,
          average_ticket: 0,
          products: [],
          daily: [],
          representative_totals: [],
        };

    return NextResponse.json({
      ...dashboard,
      metrics: safeMetrics,
      secretary_instances: canViewResults
        ? (instances.instances || []).filter((instance) => instance.agent_type === "secretary")
        : [],
      can_view_results: canViewResults,
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar IA Secretaria" },
      { status: 500 }
    );
  }
}
