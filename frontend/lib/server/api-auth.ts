import { NextResponse } from "next/server";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/server";
import type { Role } from "@/lib/types";

export const API_ROLES = {
  ALL: ["master_dev", "admin", "gestor", "representante"] as Role[],
  GESTOR_UP: ["master_dev", "admin", "gestor"] as Role[],
  ELEVATED: ["master_dev", "admin"] as Role[],
  MASTER: ["master_dev"] as Role[],
};

type ApiProfile = {
  id: string;
  role: Role;
  ativo: boolean;
  cod_rep: number | null;
};

export type ApiAuthSuccess = {
  user: User;
  profile: ApiProfile;
};

export type ApiAuthFailure = {
  response: NextResponse;
};

export async function requireApiRole(roles: Role[] = API_ROLES.ALL): Promise<ApiAuthSuccess | ApiAuthFailure> {
  const supabase = createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return {
      response: NextResponse.json({ error: "Nao autenticado." }, { status: 401 }),
    };
  }

  const { data: profile, error: profileError } = await supabase
    .from("user_profiles")
    .select("id,role,ativo,cod_rep")
    .eq("id", user.id)
    .single<ApiProfile>();

  if (profileError || !profile?.ativo) {
    return {
      response: NextResponse.json({ error: "Usuario sem perfil ativo." }, { status: 403 }),
    };
  }

  if (!roles.includes(profile.role)) {
    return {
      response: NextResponse.json({ error: "Sem permissao para esta acao." }, { status: 403 }),
    };
  }

  return { user, profile };
}

export function isApiAuthFailure(result: ApiAuthSuccess | ApiAuthFailure): result is ApiAuthFailure {
  return "response" in result;
}
