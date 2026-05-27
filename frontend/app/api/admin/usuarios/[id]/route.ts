import { NextResponse } from "next/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import type { Role, UserProfile } from "@/lib/types";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

const ROLES: Role[] = ["master_dev", "admin", "gestor", "representante"];
const ELEVATED: Role[] = ["master_dev", "admin"];

function asString(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function adminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    return { error: "SUPABASE_SERVICE_ROLE_KEY nao configurada." as const };
  }

  return {
    client: createSupabaseClient(url, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    }),
  };
}

async function getCurrentProfile() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { error: "Nao autenticado." as const, status: 401 as const };

  const { data: profile } = await supabase
    .from("user_profiles")
    .select("id,role,ativo")
    .eq("id", user.id)
    .single<Pick<UserProfile, "id" | "role" | "ativo">>();

  if (!profile?.ativo || !ELEVATED.includes(profile.role)) {
    return { error: "Sem permissao para gerenciar usuarios." as const, status: 403 as const };
  }

  return { user, profile };
}

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  const current = await getCurrentProfile();
  if ("error" in current) {
    return NextResponse.json({ error: current.error }, { status: current.status });
  }

  const admin = adminClient();
  if ("error" in admin) {
    return NextResponse.json({ error: admin.error }, { status: 500 });
  }

  const { data: profile, error: profileError } = await admin.client
    .from("user_profiles")
    .select("id,role,cod_rep,cpf,nome,ativo,created_at,updated_at")
    .eq("id", params.id)
    .single<UserProfile>();

  if (profileError || !profile) {
    return NextResponse.json({ error: "Usuario nao encontrado." }, { status: 404 });
  }

  const { data: userData, error: userError } = await admin.client.auth.admin.getUserById(params.id);

  if (userError || !userData.user) {
    return NextResponse.json({ error: userError?.message || "Auth user nao encontrado." }, { status: 404 });
  }

  return NextResponse.json({
    ...profile,
    email: userData.user.email ?? "",
  });
}

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const auth = await requireApiRole(API_ROLES.ELEVATED);
  if (isApiAuthFailure(auth)) return auth.response;

  const current = await getCurrentProfile();
  if ("error" in current) {
    return NextResponse.json({ error: current.error }, { status: current.status });
  }

  const admin = adminClient();
  if ("error" in admin) {
    return NextResponse.json({ error: admin.error }, { status: 500 });
  }

  const body = await request.json();
  const email = asString(body.email).toLowerCase();
  const password = asString(body.password);
  const nome = asString(body.nome);
  const role = asString(body.role) as Role;
  const cpf = asString(body.cpf) || null;
  const codRepValue = asString(body.cod_rep);
  const cod_rep = codRepValue ? Number(codRepValue) : null;
  const ativo = body.ativo !== false;

  if (!email || !nome || !ROLES.includes(role)) {
    return NextResponse.json({ error: "Preencha e-mail, nome e cargo." }, { status: 400 });
  }

  if (password && password.length < 6) {
    return NextResponse.json({ error: "A nova senha precisa ter pelo menos 6 caracteres." }, { status: 400 });
  }

  if (codRepValue && !Number.isFinite(cod_rep)) {
    return NextResponse.json({ error: "Codigo do representante invalido." }, { status: 400 });
  }

  const { data: existingProfile, error: existingError } = await admin.client
    .from("user_profiles")
    .select("id,role,ativo")
    .eq("id", params.id)
    .single<Pick<UserProfile, "id" | "role" | "ativo">>();

  if (existingError || !existingProfile) {
    return NextResponse.json({ error: "Usuario nao encontrado." }, { status: 404 });
  }

  const { data: existingUserData, error: existingUserError } = await admin.client.auth.admin.getUserById(params.id);

  if (existingUserError || !existingUserData.user) {
    return NextResponse.json(
      { error: existingUserError?.message || "Auth user nao encontrado." },
      { status: 404 }
    );
  }

  const isSelf = params.id === current.profile.id;
  const currentEmail = existingUserData.user.email ?? "";
  const changingRestrictedFields = Boolean(password) || role !== existingProfile.role || email !== currentEmail;

  if (current.profile.role !== "master_dev" && changingRestrictedFields) {
    return NextResponse.json(
      { error: "Apenas Master Dev pode alterar e-mail, senha ou cargo." },
      { status: 403 }
    );
  }

  if (isSelf && !ativo) {
    return NextResponse.json({ error: "Voce nao pode desativar seu proprio usuario." }, { status: 400 });
  }

  const authUpdates: { email?: string; password?: string; email_confirm?: boolean; user_metadata: { nome: string } } = {
    user_metadata: { nome },
  };

  if (current.profile.role === "master_dev") {
    authUpdates.email = email;
    authUpdates.email_confirm = true;
    if (password) {
      authUpdates.password = password;
    }
  }

  const { error: authError } = await admin.client.auth.admin.updateUserById(params.id, authUpdates);
  if (authError) {
    return NextResponse.json({ error: authError.message }, { status: authError.status || 400 });
  }

  const { error: profileError } = await admin.client
    .from("user_profiles")
    .update({
      nome,
      role,
      cod_rep,
      cpf,
      ativo,
    })
    .eq("id", params.id);

  if (profileError) {
    return NextResponse.json({ error: profileError.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
