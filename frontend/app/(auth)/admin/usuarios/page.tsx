"use client";

import { useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { createClient } from "@/lib/supabase/client";
import { useAuth } from "@/lib/auth-context";
import type { UserProfile, Role } from "@/lib/types";
import Link from "next/link";
import { UserPlus, RefreshCw } from "lucide-react";

const ROLE_LABELS: Record<Role, string> = {
  master_dev:    "Master Dev",
  admin:         "Admin",
  gestor:        "Gestor",
  representante: "Representante",
};

const ROLE_COLORS: Record<Role, string> = {
  master_dev:    "var(--accent)",
  admin:         "var(--success)",
  gestor:        "var(--warn)",
  representante: "var(--muted)",
};

export default function UsuariosPage() {
  const { profile: currentProfile } = useAuth();
  const [usuarios, setUsuarios] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    loadUsuarios();
  }, []);

  async function loadUsuarios() {
    setLoading(true);
    const supabase = createClient();
    const { data } = await supabase
      .from("user_profiles")
      .select("id,role,cod_rep,cpf,nome,ativo,created_at,updated_at")
      .order("created_at", { ascending: false });
    setUsuarios(data ?? []);
    setLoading(false);
  }

  async function toggleAtivo(id: string, currentAtivo: boolean) {
    setSaving(id);
    const supabase = createClient();
    await supabase
      .from("user_profiles")
      .update({ ativo: !currentAtivo })
      .eq("id", id);
    setUsuarios((prev) =>
      prev.map((u) => (u.id === id ? { ...u, ativo: !currentAtivo } : u))
    );
    setSaving(null);
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Usuários" />
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 24,
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
              Gerenciar Usuários
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--muted)" }}>
              {usuarios.length} usuário{usuarios.length !== 1 ? "s" : ""} cadastrado{usuarios.length !== 1 ? "s" : ""}
            </p>
          </div>
          {currentProfile?.role === "master_dev" && (
            <Link
              href="/admin/usuarios/novo"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 18px",
                background: "var(--accent)",
                color: "#fff",
                borderRadius: 8,
                textDecoration: "none",
                fontSize: 13,
                fontWeight: 600,
                boxShadow: "0 0 12px var(--accent-glow)",
              }}
            >
              <UserPlus size={14} />
              Novo Usuário
            </Link>
          )}
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
            Carregando...
          </div>
        ) : (
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              overflow: "hidden",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Nome", "Cargo", "Cód. Rep", "Status", "Desde", "Ações"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "12px 16px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr
                    key={u.id}
                    style={{
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <td style={{ padding: "12px 16px", color: "var(--text)", fontSize: 13, fontWeight: 500 }}>
                      {u.nome}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span
                        style={{
                          padding: "3px 10px",
                          borderRadius: 12,
                          background: `${ROLE_COLORS[u.role]}18`,
                          color: ROLE_COLORS[u.role],
                          border: `1px solid ${ROLE_COLORS[u.role]}44`,
                          fontSize: 11,
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: 0.3,
                        }}
                      >
                        {ROLE_LABELS[u.role]}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", color: "var(--muted)", fontSize: 13 }}>
                      {u.cod_rep ?? "—"}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          color: u.ativo ? "var(--success)" : "var(--error)",
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        <span
                          style={{
                            width: 7,
                            height: 7,
                            borderRadius: "50%",
                            background: u.ativo ? "var(--success)" : "var(--error)",
                          }}
                        />
                        {u.ativo ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", color: "var(--muted)", fontSize: 12 }}>
                      {new Date(u.created_at).toLocaleDateString("pt-BR")}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Link
                          href={`/admin/usuarios/${u.id}`}
                          style={{
                            fontSize: 12,
                            color: "var(--accent)",
                            textDecoration: "none",
                            fontWeight: 500,
                          }}
                        >
                          Editar
                        </Link>
                        {u.id !== currentProfile?.id && (
                          <button
                            onClick={() => toggleAtivo(u.id, u.ativo)}
                            disabled={saving === u.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 4,
                              fontSize: 12,
                              padding: "3px 10px",
                              border: `1px solid ${u.ativo ? "var(--error)" : "var(--success)"}`,
                              borderRadius: 5,
                              background: "none",
                              cursor: saving === u.id ? "not-allowed" : "pointer",
                              color: u.ativo ? "var(--error)" : "var(--success)",
                              opacity: saving === u.id ? 0.6 : 1,
                            }}
                          >
                            {saving === u.id && <RefreshCw size={10} />}
                            {u.ativo ? "Desativar" : "Ativar"}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
