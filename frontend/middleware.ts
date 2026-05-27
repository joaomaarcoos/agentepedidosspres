import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { API_ROUTE_RULES, PUBLIC_API_PATHS, PUBLIC_PATHS, ROUTE_RULES } from "@/lib/auth";
import type { UserProfile } from "@/lib/types";

function isPathMatch(pathname: string, basePath: string) {
  return pathname === basePath || pathname.startsWith(`${basePath}/`);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Passa direto: paths públicos, internals do Next e arquivos estáticos
  if (
    PUBLIC_PATHS.some((p) => isPathMatch(pathname, p)) ||
    PUBLIC_API_PATHS.some((p) => isPathMatch(pathname, p)) ||
    isPathMatch(pathname, "/api/evolution/webhook") ||
    pathname.startsWith("/_next") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    (process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL)!,
    (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY)!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Valida sessão com o servidor (getUser é seguro; getSession pode ser forjado)
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Nao autenticado." }, { status: 401 });
    }

    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Busca perfil para verificar role
  const { data: profile } = await supabase
    .from("user_profiles")
    .select("id,role,cod_rep,ativo")
    .eq("id", user.id)
    .single<Pick<UserProfile, "id" | "role" | "cod_rep" | "ativo">>();

  if (!profile || !profile.ativo) {
    await supabase.auth.signOut();
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Usuario inativo ou sem perfil." }, { status: 403 });
    }

    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Verifica permissão de rota
  const rules = pathname.startsWith("/api/") ? API_ROUTE_RULES : ROUTE_RULES;
  const rule = rules.find((r) => r.pattern.test(pathname));
  if (pathname.startsWith("/api/") && !rule) {
    return NextResponse.json({ error: "Rota de API nao autorizada." }, { status: 403 });
  }

  if (rule && !rule.roles.includes(profile.role)) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Sem permissao." }, { status: 403 });
    }

    return NextResponse.redirect(new URL("/acesso-negado", request.url));
  }

  // Passa role e id como headers para server components downstream
  response.headers.set("x-user-id", profile.id);
  response.headers.set("x-user-role", profile.role);
  if (profile.cod_rep !== null) {
    response.headers.set("x-user-cod-rep", String(profile.cod_rep));
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
