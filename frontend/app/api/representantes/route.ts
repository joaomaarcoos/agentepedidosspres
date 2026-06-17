import { NextResponse } from "next/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RepresentativeProfile = {
  cod_rep?: number;
  documento?: string | null;
  nome?: string | null;
  razao_social?: string | null;
  fantasia?: string | null;
};

export async function GET() {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) {
    return NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY nao configurada." }, { status: 500 });
  }

  const supabase = createSupabaseClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const [{ data: reps, error: repsError }, { data: profileRows }, { data: orderRows }] = await Promise.all([
    supabase.from("representatives").select("cod_rep,name,active,whatsapp_number").order("name"),
    supabase.from("system_settings").select("value").eq("key", "clic_representative_profiles").limit(1),
    supabase.from("rep_order_base").select("cod_rep,cod_cli").limit(20000),
  ]);

  if (repsError) {
    return NextResponse.json({ error: repsError.message }, { status: 500 });
  }

  const profiles = ((profileRows?.[0]?.value || {}) as Record<string, RepresentativeProfile>);
  const stats = new Map<number, { orders: number; customers: Set<number> }>();
  for (const row of orderRows || []) {
    const codRep = Number(row.cod_rep);
    if (!Number.isFinite(codRep)) continue;
    const current = stats.get(codRep) || { orders: 0, customers: new Set<number>() };
    current.orders += 1;
    const codCli = Number(row.cod_cli);
    if (Number.isFinite(codCli)) current.customers.add(codCli);
    stats.set(codRep, current);
  }

  const representantes = (reps || []).map((rep) => {
    const profile = profiles[String(rep.cod_rep)] || {};
    const stat = stats.get(Number(rep.cod_rep));
    return {
      cod_rep: Number(rep.cod_rep),
      name: profile.nome || profile.razao_social || rep.name || `Representante ${rep.cod_rep}`,
      document: profile.documento || null,
      active: rep.active !== false,
      whatsapp_number: rep.whatsapp_number || null,
      orders_count: stat?.orders || 0,
      customers_count: stat?.customers.size || 0,
    };
  });

  return NextResponse.json({ representantes });
}
