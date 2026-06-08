import { NextResponse } from "next/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import type { Role } from "@/lib/types";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

const ROLES: Role[] = ["master_dev", "admin", "gestor", "representante"];

function asString(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

export async function POST(request: Request) {
  const auth = await requireApiRole(API_ROLES.GESTOR_UP);
  if (isApiAuthFailure(auth)) return auth.response;

  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Nao autenticado." }, { status: 401 });
  }

  const { data: currentProfile } = await supabase
    .from("user_profiles")
    .select("role,ativo")
    .eq("id", user.id)
    .single<{ role: Role; ativo: boolean }>();

  if (!currentProfile?.ativo || !["master_dev", "admin", "gestor"].includes(currentProfile.role)) {
    return NextResponse.json({ error: "Sem permissao para criar usuarios." }, { status: 403 });
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

  if (!email || !password || !nome || !ROLES.includes(role)) {
    return NextResponse.json({ error: "Preencha e-mail, senha, nome e cargo." }, { status: 400 });
  }

  if (currentProfile.role !== "master_dev" && role === "master_dev") {
    return NextResponse.json({ error: "Somente Master Dev pode criar usuario Master Dev." }, { status: 403 });
  }

  if (currentProfile.role === "gestor" && role !== "representante") {
    return NextResponse.json({ error: "Gestor pode criar somente usuarios representantes." }, { status: 403 });
  }

  if (password.length < 6) {
    return NextResponse.json({ error: "A senha precisa ter pelo menos 6 caracteres." }, { status: 400 });
  }

  if (codRepValue && !Number.isFinite(cod_rep)) {
    return NextResponse.json({ error: "Codigo do representante invalido." }, { status: 400 });
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    return NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY nao configurada." }, { status: 500 });
  }

  const admin = createSupabaseClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: created, error: createError } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { nome },
  });

  if (createError || !created.user) {
    return NextResponse.json(
      { error: createError?.message || "Nao foi possivel criar o usuario." },
      { status: createError?.status || 400 }
    );
  }

  const { error: profileError } = await admin.from("user_profiles").insert({
    id: created.user.id,
    role,
    cod_rep,
    cpf,
    nome,
    ativo,
  });

  if (profileError) {
    await admin.auth.admin.deleteUser(created.user.id);
    return NextResponse.json({ error: profileError.message }, { status: 400 });
  }

  return NextResponse.json({ id: created.user.id });
}
