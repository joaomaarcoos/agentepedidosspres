import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";

export async function POST(request: NextRequest) {
  const contentType = request.headers.get("content-type") || "";
  const isFormPost = contentType.includes("application/x-www-form-urlencoded");
  let email = "";
  let password = "";
  let next = "/pedidos";

  if (isFormPost) {
    const formData = await request.formData();
    email = String(formData.get("email") || "");
    password = String(formData.get("password") || "");
    next = String(formData.get("next") || "/pedidos");
  } else {
    const body = await request.json();
    email = String(body.email || "");
    password = String(body.password || "");
    next = String(body.next || "/pedidos");
  }

  if (!next.startsWith("/") || next.startsWith("//")) {
    next = "/pedidos";
  }

  if (!email || !password) {
    if (isFormPost) {
      return NextResponse.redirect(new URL("/login?error=Preencha%20e-mail%20e%20senha.", request.url), {
        status: 303,
      });
    }
    return NextResponse.json({ error: "Preencha e-mail e senha." }, { status: 400 });
  }

  let response = isFormPost
    ? NextResponse.redirect(new URL(next, request.url), { status: 303 })
    : NextResponse.json({ ok: true });

  const supabase = createServerClient(
    (process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL)!,
    (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY)!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  const { error } = await supabase.auth.signInWithPassword({
    email: String(email).trim(),
    password: String(password),
  });

  if (error) {
    if (isFormPost) {
      return NextResponse.redirect(new URL("/login?error=E-mail%20ou%20senha%20incorretos.", request.url), {
        status: 303,
      });
    }

    return NextResponse.json(
      {
        error:
          process.env.NODE_ENV === "development" && error.message
            ? error.message
            : "E-mail ou senha incorretos.",
      },
      { status: error.status || 401 }
    );
  }

  return response;
}
