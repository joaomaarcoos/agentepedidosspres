"use client";

import { useEffect, useState } from "react";
import { statusApi } from "@/lib/api";

export default function Header({ title }: { title?: string }) {
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    statusApi
      .check()
      .then((r) => setApiOk(r.ok))
      .catch(() => setApiOk(false));
  }, []);

  return (
    <header
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
      <span style={{ fontWeight: 600, fontSize: 15, color: "var(--text)" }}>
        {title || "AgentePedidos"}
      </span>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
