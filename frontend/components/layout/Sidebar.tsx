"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart2,
  BrainCircuit,
  ClipboardCheck,
  FileText,
  LogOut,
  Package,
  Repeat2,
  Settings2,
  ShoppingCart,
  Tag,
  User,
  Users,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { NAV_ITEMS } from "@/lib/auth";

const ICON_MAP: Record<string, React.ElementType> = {
  "/pedidos":        ShoppingCart,
  "/clientes":       Users,
  "/recorrencia":    Repeat2,
  "/ativacao":       Zap,
  "/resultados":     BarChart2,
  "/logs":           FileText,
  "/produtos":       Package,
  "/tabela-preco":   Tag,
  "/revisaopedido":  ClipboardCheck,
  "/conexao":        Activity,
  "/agente-studio":  BrainCircuit,
  "/admin/usuarios": Settings2,
  "/perfil":         User,
};

const ROLE_LABEL: Record<string, string> = {
  master_dev:    "Master Dev",
  admin:         "Admin",
  gestor:        "Gestor",
  representante: "Representante",
};

export default function Sidebar() {
  const pathname = usePathname();
  const { profile, loading, signOut } = useAuth();

  const visibleNav = profile
    ? NAV_ITEMS.filter((item) => (item.roles as readonly string[]).includes(profile.role))
    : [];

  return (
    <aside
      style={{
        width: 220,
        minWidth: 220,
        background: "var(--surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "16px 0",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {/* Branding */}
      <div style={{ padding: "0 20px 20px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              background: "var(--accent)",
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              color: "#fff",
              fontSize: 14,
              boxShadow: "0 0 15px var(--accent-glow)",
            }}
          >
            A
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text)" }}>
              Agente<span style={{ color: "var(--accent)" }}>Pedidos</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>SucosSpres</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "12px 8px", overflowY: "auto" }}>
        {loading ? (
          <div style={{ padding: "12px 12px", fontSize: 12, color: "var(--muted)" }}>
            Carregando...
          </div>
        ) : (
          visibleNav.map(({ href, label }) => {
            const Icon = ICON_MAP[href] || ShoppingCart;
            const isActive = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 12px",
                  borderRadius: 8,
                  marginBottom: 2,
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#fff" : "var(--muted)",
                  background: isActive ? "var(--accent)" : "transparent",
                  textDecoration: "none",
                  transition: "background 0.15s, color 0.15s",
                }}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })
        )}
      </nav>

      {/* Usuário + Logout */}
      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border)",
        }}
      >
        {profile && (
          <div style={{ marginBottom: 10 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {profile.nome}
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--accent)",
                textTransform: "uppercase",
                letterSpacing: 0.5,
                marginTop: 2,
              }}
            >
              {ROLE_LABEL[profile.role] ?? profile.role}
            </div>
          </div>
        )}
        <button
          onClick={signOut}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "none",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "7px 10px",
            cursor: "pointer",
            color: "var(--muted)",
            fontSize: 12,
            width: "100%",
            transition: "color 0.15s, border-color 0.15s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.color = "var(--error)";
            (e.currentTarget as HTMLElement).style.borderColor = "var(--error)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.color = "var(--muted)";
            (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
          }}
        >
          <LogOut size={13} />
          Sair
        </button>
      </div>
    </aside>
  );
}
