"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import type { Role } from "@/lib/types";
import { ArrowLeft, Eye, EyeOff, Save } from "lucide-react";
import Link from "next/link";

const ROLES: Role[] = ["master_dev", "admin", "gestor", "representante"];
const ROLE_LABELS: Record<Role, string> = {
  master_dev: "Master Dev",
  admin: "Admin",
  gestor: "Gestor",
  representante: "Representante",
};

export default function NovoUsuarioPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [nome, setNome] = useState("");
  const [role, setRole] = useState<Role>("gestor");
  const [codRep, setCodRep] = useState("");
  const [cpf, setCpf] = useState("");
  const [ativo, setAtivo] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (saving) return;

    setSaving(true);
    setError(null);

    const response = await fetch("/api/admin/usuarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        nome,
        role,
        cod_rep: codRep,
        cpf,
        ativo,
      }),
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      setError(data?.error || "Nao foi possivel criar o usuario.");
      setSaving(false);
      return;
    }

    router.push("/admin/usuarios");
    router.refresh();
  }

  const fieldStyle = {
    width: "100%",
    padding: "10px 14px",
    background: "var(--surface2)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text)",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box" as const,
  };

  const labelStyle = {
    display: "block" as const,
    fontSize: 12,
    color: "var(--muted)",
    marginBottom: 6,
    fontWeight: 500 as const,
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Novo Usuario" />
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <Link
          href="/admin/usuarios"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: "var(--muted)",
            textDecoration: "none",
            marginBottom: 24,
          }}
        >
          <ArrowLeft size={14} />
          Voltar para Usuarios
        </Link>

        <div
          style={{
            maxWidth: 520,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: 28,
          }}
        >
          <h2 style={{ margin: "0 0 24px", fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
            Adicionar usuario
          </h2>

          {error && (
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(248,113,113,0.1)",
                border: "1px solid rgba(248,113,113,0.3)",
                borderRadius: 8,
                color: "var(--error)",
                fontSize: 13,
                marginBottom: 20,
              }}
            >
              {error}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div>
              <label style={labelStyle}>Nome</label>
              <input
                type="text"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Nome completo"
                style={fieldStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>E-mail</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@email.com"
                style={fieldStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>Senha inicial</label>
              <div style={{ position: "relative", width: "100%" }}>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimo 6 caracteres"
                  style={{ ...fieldStyle, paddingRight: 44 }}
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

            <div>
              <label style={labelStyle}>Cargo</label>
              <select value={role} onChange={(e) => setRole(e.target.value as Role)} style={fieldStyle}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={labelStyle}>Codigo do Representante (cod_rep)</label>
              <input
                type="number"
                value={codRep}
                onChange={(e) => setCodRep(e.target.value)}
                placeholder="Ex: 4"
                style={fieldStyle}
              />
            </div>

            <div>
              <label style={labelStyle}>CPF</label>
              <input
                type="text"
                value={cpf}
                onChange={(e) => setCpf(e.target.value)}
                placeholder="000.000.000-00"
                style={fieldStyle}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                type="checkbox"
                id="ativo"
                checked={ativo}
                onChange={(e) => setAtivo(e.target.checked)}
                style={{ width: 16, height: 16, cursor: "pointer" }}
              />
              <label htmlFor="ativo" style={{ fontSize: 13, color: "var(--text)", cursor: "pointer" }}>
                Usuario ativo
              </label>
            </div>

            <button
              onClick={handleCreate}
              disabled={saving}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                padding: "11px 0",
                background: saving ? "var(--border)" : "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 14,
                cursor: saving ? "not-allowed" : "pointer",
                boxShadow: saving ? "none" : "0 0 12px var(--accent-glow)",
                marginTop: 8,
              }}
            >
              <Save size={14} />
              {saving ? "Criando..." : "Criar usuario"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
