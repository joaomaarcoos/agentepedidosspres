"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { createClient } from "@/lib/supabase/client";
import { useAuth } from "@/lib/auth-context";
import type { Role } from "@/lib/types";
import { Save } from "lucide-react";

const ROLE_LABELS: Record<Role, string> = {
  master_dev:    "Master Dev",
  admin:         "Admin",
  gestor:        "Gestor",
  representante: "Representante",
};

export default function PerfilPage() {
  const { profile, loading: authLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [cpf, setCpf] = useState("");
  const [codRep, setCodRep] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setNome(profile.nome);
    setCpf(profile.cpf ?? "");
    setCodRep(profile.cod_rep !== null ? String(profile.cod_rep) : "");

    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      if (data.user?.email) setEmail(data.user.email);
    });
  }, [profile]);

  async function handleSave() {
    if (!profile) return;
    setSaving(true);
    setError(null);
    setSuccess(false);

    const supabase = createClient();
    const { error: updateError } = await supabase
      .from("user_profiles")
      .update({
        nome: nome.trim(),
        cpf: cpf.trim() || null,
        cod_rep: codRep ? Number(codRep) : null,
      })
      .eq("id", profile.id);

    if (updateError) {
      setError(updateError.message);
    } else {
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    }
    setSaving(false);
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

  const disabledFieldStyle = {
    ...fieldStyle,
    opacity: 0.6,
    cursor: "not-allowed" as const,
  };

  const labelStyle = {
    display: "block" as const,
    fontSize: 12,
    color: "var(--muted)",
    marginBottom: 6,
    fontWeight: 500 as const,
  };

  if (authLoading) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <Header title="Meu Perfil" />
        <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Meu Perfil" />
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div
          style={{
            maxWidth: 480,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: 28,
          }}
        >
          <h2 style={{ margin: "0 0 6px", fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
            Informações da conta
          </h2>
          <p style={{ margin: "0 0 24px", fontSize: 13, color: "var(--muted)" }}>
            Edite seus dados pessoais e de representante.
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
                marginBottom: 20,
              }}
            >
              {error}
            </div>
          )}
          {success && (
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(52,211,153,0.1)",
                border: "1px solid rgba(52,211,153,0.3)",
                borderRadius: 8,
                color: "var(--success)",
                fontSize: 13,
                marginBottom: 20,
              }}
            >
              Perfil atualizado com sucesso!
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div>
              <label style={labelStyle}>E-mail</label>
              <input
                type="email"
                value={email}
                disabled
                style={disabledFieldStyle}
              />
              <span style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, display: "block" }}>
                O e-mail não pode ser alterado aqui.
              </span>
            </div>

            <div>
              <label style={labelStyle}>Cargo</label>
              <input
                type="text"
                value={profile ? ROLE_LABELS[profile.role] : ""}
                disabled
                style={disabledFieldStyle}
              />
              <span style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, display: "block" }}>
                Somente um administrador pode alterar seu cargo.
              </span>
            </div>

            <div>
              <label style={labelStyle}>Nome completo</label>
              <input
                type="text"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Seu nome"
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

            <div>
              <label style={labelStyle}>Código do Representante (cod_rep)</label>
              <input
                type="number"
                value={codRep}
                onChange={(e) => setCodRep(e.target.value)}
                placeholder="Ex: 4"
                style={fieldStyle}
              />
              <span style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, display: "block" }}>
                Necessário para o cargo de representante.
              </span>
            </div>

            <button
              onClick={handleSave}
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
              {saving ? "Salvando..." : "Salvar Perfil"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
