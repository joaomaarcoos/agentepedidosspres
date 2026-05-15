"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart2, BrainCircuit, ClipboardCheck, FileText, Package, Repeat2, ShoppingCart, Users, Zap } from "lucide-react";

const nav = [
  { href: "/pedidos", label: "Pedidos", icon: ShoppingCart },
  { href: "/revisaopedido", label: "Revisão Pedidos", icon: ClipboardCheck },
  { href: "/produtos", label: "Produtos", icon: Package },
  { href: "/conexao", label: "Conexão", icon: Activity },
  { href: "/clientes", label: "Clientes", icon: Users },
  { href: "/recorrencia", label: "Recorrência", icon: Repeat2 },
  { href: "/ativacao", label: "Ativação", icon: Zap },
  { href: "/resultados", label: "Resultados", icon: BarChart2 },
  { href: "/logs", label: "Logs Disparos", icon: FileText },
  { href: "/agente-studio", label: "Agente Studio", icon: BrainCircuit },
];

export default function Sidebar() {
  const pathname = usePathname();

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

      <nav style={{ flex: 1, padding: "12px 8px", overflowY: "auto" }}>
        {nav.map(({ href, label, icon: Icon }) => {
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
        })}
      </nav>

      <div
        style={{
          padding: "12px 20px",
          borderTop: "1px solid var(--border)",
          fontSize: 11,
          color: "var(--muted)",
        }}
      >
        v1.0.0 · Next.js + Python interno
      </div>
    </aside>
  );
}
