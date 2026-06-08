"use client";

import { Suspense, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";

const SUCOS_SPRES_LOGO_URL =
  "https://tsnvhhrifxcnuszzaxfk.supabase.co/storage/v1/object/public/app-assets/brand/sucos-spres-logo.png";

function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/pedidos";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(searchParams.get("error"));
  const submittingRef = useRef(false);

  async function handleLogin(source: string = "submit") {
    if (submittingRef.current) return;

    if (!email || !password) {
      setError("Preencha e-mail e senha.");
      return;
    }

    submittingRef.current = true;
    setLoading(true);
    setError(null);
    console.info("Iniciando login:", { source, email: email.trim() });

    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 15000);

      const result = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          next,
        }),
        signal: controller.signal,
      });
      window.clearTimeout(timeout);

      if (!result.ok) {
        const data = await result.json().catch(() => null);
        setError(data?.error || "E-mail ou senha incorretos.");
        submittingRef.current = false;
        setLoading(false);
        return;
      }

      console.info("Login concluido. Redirecionando:", next);
      window.location.assign(next);
    } catch (err) {
      console.error("Erro no login:", err);
      setError("Nao foi possivel concluir o login. Verifique a conexao e tente novamente.");
      submittingRef.current = false;
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await handleLogin("submit");
  }

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg)",
      }}
    >
      <div
        style={{
          width: 380,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 36,
          boxShadow: "0 8px 40px rgba(0,0,0,0.5)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 28 }}>
          <img
            src={SUCOS_SPRES_LOGO_URL}
            alt="Sucos Spres"
            style={{
              width: 58,
              height: 46,
              borderRadius: 8,
              objectFit: "contain",
              background: "#fff",
              boxShadow: "0 0 20px var(--accent-glow)",
            }}
          />
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "var(--text)" }}>
              Agente<span style={{ color: "var(--accent)" }}>Pedidos</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>SucosSpres</div>
          </div>
        </div>

        <h1 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 700, color: "var(--text)" }}>
          Entrar
        </h1>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "var(--muted)" }}>
          Acesse sua conta para continuar
        </p>

        {error && (
          <div
            style={{
              padding: "10px 14px",
              background: "rgba(248,113,113,0.1)",
              border: "1px solid rgba(248,113,113,0.3)",
              borderRadius: 8,
              color: "var(--error)",
              fontSize: 13,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        <form
          action="/api/auth/login"
          method="post"
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", gap: 14 }}
        >
          <input type="hidden" name="next" value={next} />
          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                color: "var(--muted)",
                marginBottom: 6,
                fontWeight: 500,
              }}
            >
              E-mail
            </label>
            <input
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                background: "var(--surface2)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                color: "var(--text)",
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label
              style={{
                display: "block",
                fontSize: 12,
                color: "var(--muted)",
                marginBottom: 6,
                fontWeight: 500,
              }}
            >
              Senha
            </label>
            <div style={{ position: "relative", width: "100%" }}>
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="********"
                required
                style={{
                  width: "100%",
                  padding: "10px 44px 10px 14px",
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 14,
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <button
                type="button"
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                title={showPassword ? "Ocultar senha" : "Mostrar senha"}
                onClick={() => setShowPassword((value) => !value)}
                style={{
                  position: "absolute",
                  top: "50%",
                  right: 10,
                  transform: "translateY(-50%)",
                  width: 28,
                  height: 28,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "transparent",
                  border: "none",
                  borderRadius: 6,
                  color: "var(--muted)",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 6,
              padding: "11px 0",
              background: loading ? "var(--border)" : "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontWeight: 600,
              fontSize: 14,
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background 0.15s",
              boxShadow: loading ? "none" : "0 0 14px var(--accent-glow)",
            }}
          >
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
