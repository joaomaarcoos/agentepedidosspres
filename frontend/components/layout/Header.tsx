"use client";

import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { statusApi } from "@/lib/api";
import { useShell } from "@/components/layout/ShellContext";

export default function Header({ title }: { title?: string }) {
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const { toggleSidebar } = useShell();

  useEffect(() => {
    statusApi
      .check()
      .then((r) => setApiOk(r.ok))
      .catch(() => setApiOk(false));
  }, []);

  return (
    <header
      className="app-header"
      style={{
        height: 52,
        minHeight: 52,
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
      }}
    >
      <div className="app-header-left">
        <button className="app-menu-toggle" onClick={toggleSidebar} aria-label="Expandir ou ocultar menu">
          <Menu size={18} />
        </button>
        <span className="app-header-title" style={{ fontWeight: 600, fontSize: 15, color: "var(--text)" }}>
          {title || "AgentePedidos"}
        </span>
      </div>

      <div className="app-header-actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            color: "var(--muted)",
            padding: "4px 12px",
            background: "rgba(0,0,0,0.2)",
            borderRadius: 20,
            border: "1px solid var(--border)",
            fontSize: 12,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background:
                apiOk === null
                  ? "var(--muted)"
                  : apiOk
                  ? "var(--success)"
                  : "var(--error)",
              boxShadow: apiOk ? "0 0 6px var(--success)" : undefined,
              display: "inline-block",
            }}
          />
          API {apiOk === null ? "..." : apiOk ? "Online" : "Offline"}
        </div>
      </div>
    </header>
  );
}
