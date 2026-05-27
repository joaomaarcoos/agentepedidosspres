import { NextResponse } from "next/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import { API_ROLES, isApiAuthFailure, requireApiRole } from "@/lib/server/api-auth";

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

export async function PATCH(request: Request) {
  const auth = await requireApiRole(API_ROLES.ALL);
  if (isApiAuthFailure(auth)) return auth.response;

  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Nao autenticado." }, { status: 401 });
  }

  const body = await request.json();
  const email = asString(body.email).toLowerCase();
  const password = asString(body.password);
  const nome = asString(body.nome);
  const cpf = asString(body.cpf) || null;
  const codRepValue = asString(body.cod_rep);
  const cod_rep = codRepValue ? Number(codRepValue) : null;

  if (!email || !nome) {
    return NextResponse.json({ error: "Preencha e-mail e nome." }, { status: 400 });
  }

  if (password && password.length < 6) {
    return NextResponse.json({ error: "A nova senha precisa ter pelo menos 6 caracteres." }, { status: 400 });
  }

  if (codRepValue && !Number.isFinite(cod_rep)) {
    return NextResponse.json({ error: "Codigo do representante invalido." }, { status: 400 });
  }

  const admin = adminClient();
  if ("error" in admin) {
    return NextResponse.json({ error: admin.error }, { status: 500 });
  }

  const authUpdates: {
    email: string;
    password?: string;
    email_confirm: boolean;
    user_metadata: { nome: string };
  } = {
    email,
    email_confirm: true,
    user_metadata: { nome },
  };

  if (password) {
    authUpdates.password = password;
  }

  const { error: authError } = await admin.client.auth.admin.updateUserById(user.id, authUpdates);

  if (authError) {
    return NextResponse.json({ error: authError.message }, { status: authError.status || 400 });
  }

  const { error: profileError } = await admin.client
    .from("user_profiles")
    .update({
      nome,
      cpf,
      cod_rep,
    })
    .eq("id", user.id);

  if (profileError) {
    return NextResponse.json({ error: profileError.message }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
