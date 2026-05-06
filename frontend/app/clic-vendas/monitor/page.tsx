"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import { clicVendasApi } from "@/lib/api";
import type { SyncLog } from "@/lib/types";
import { RefreshCw, ChevronDown, ChevronUp, AlertCircle, CheckCircle, Clock, XCircle } from "lucide-react";
import Link from "next/link";

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <CheckCircle size={16} color="var(--success)" />;
  if (status === "error") return <XCircle size={16} color="var(--error)" />;
  if (status === "running") return <Clock size={16} color="var(--accent)" />;
  return <AlertCircle size={16} color="var(--warn)" />;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    success: { bg: "rgba(52,211,153,0.12)", color: "var(--success)", label: "Sucesso" },
    error: { bg: "rgba(248,113,113,0.12)", color: "var(--error)", label: "Erro" },
    running: { bg: "rgba(91,141,238,0.12)", color: "var(--accent)", label: "Executando" },
    partial: { bg: "rgba(251,191,36,0.12)", color: "var(--warn)", label: "Parcial" },
  };
  const s = map[status] || { bg: "rgba(139,155,180,0.12)", color: "var(--muted)", label: status };
  return (
    <span
      style={{
        padding: "3px 12px",
        borderRadius: 20,
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.color}`,
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
      }}
    >
      {s.label}
    </span>
  );
}

function LogRow({ log }: { log: SyncLog }) {
  const [expanded, setExpanded] = useState(false);

  const summary = log.result_summary_json;
  const statusBreakdown = summary?.status_breakdown || {};

  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        transition: "background 0.1s",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "180px 1fr 100px 80px 80px 80px 100px 40px",
          alignItems: "center",
          padding: "12px 20px",
          cursor: "pointer",
          gap: 8,
        }}
        onClick={() => setExpanded((v) => !v)}
        onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--surface2)")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "transparent")}
      >
        <span style={{ fontSize: 12, color: "var(--muted)", fontFamily: "monospace" }}>
          {new Date(log.triggered_at).toLocaleString("pt-BR")}
        </span>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <StatusIcon status={log.status} />
          <StatusBadge status={log.status} />
          {log.triggered_by && (
            <span style={{ fontSize: 11, color: "var(--muted)", padding: "2px 8px", background: "var(--surface2)", borderRadius: 4 }}>
              {log.triggered_by}
            </span>
          )}
        </div>

        <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>
          {log.total_fetched ?? 0}
        </span>
        <span style={{ fontSize: 13, color: "var(--success)" }}>{log.total_upserted ?? 0}</span>
        <span style={{ fontSize: 13, color: log.total_errors ? "var(--error)" : "var(--muted)" }}>
          {log.total_errors ?? 0}
        </span>
        <span style={{ fontSize: 12, color: "var(--muted)" }}>
          {log.duration_ms ? `${(log.duration_ms / 1000).toFixed(1)}s` : "—"}
        </span>
        <span style={{ fontSize: 11, color: "var(--muted)" }}>{summary?.total_clientes ?? "—"}</span>

        <span style={{ color: "var(--muted)" }}>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </div>

      {expanded && (
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid var(--border)",
            background: "rgba(0,0,0,0.15)",
          }}
        >
          {log.error_message && (
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(248,113,113,0.1)",
                border: "1px solid var(--error)",
                borderRadius: 8,
                color: "var(--error)",
                fontSize: 12,
                marginBottom: 12,
                fontFamily: "monospace",
              }}
            >
              {log.error_message}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
                Parâmetros
              </div>
              <div style={{ fontSize: 12, color: "var(--text)" }}>
                <div>Documento rep: <code style={{ color: "var(--accent)" }}>{log.rep_document || "—"}</code></div>
                <div>Data início: <code style={{ color: "var(--accent)" }}>{log.date_from || "—"}</code></div>
                <div>Janela: <code style={{ color: "var(--accent)" }}>{summary?.dias ?? "—"} dias</code></div>
              </div>
            </div>

            {Object.keys(statusBreakdown).length > 0 && (
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
                  Breakdown por situação
                </div>
                {Object.entries(statusBreakdown).map(([k, v]) => (
                  <div
                    key={k}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 12,
                      color: "var(--text)",
                      padding: "3px 0",
                    }}
                  >
                    <span>{k}</span>
                    <span style={{ color: "var(--accent)", fontWeight: 700 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function MonitorPage() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [logs, setLogs] = useState<SyncLog[]>([]);
  const [loading, setLoading] = useState(false);
  const hasRunning = logs.some((l) => l.status === "running");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const r = await clicVendasApi.getSyncLogs(date);
      setLogs(r.logs);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  // Auto-refresh quando há sync rodando
  useEffect(() => {
    if (hasRunning) {
      intervalRef.current = setInterval(loadLogs, 5000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [hasRunning, loadLogs]);

  const successCount = logs.filter((l) => l.status === "success").length;
  const errorCount = logs.filter((l) => l.status === "error").length;
  const runningCount = logs.filter((l) => l.status === "running").length;
  const totalFetched = logs.reduce((s, l) => s + (l.total_fetched || 0), 0);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="ClicVendas — Monitor de Sincronizações" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>
        {/* Toolbar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <Link
            href="/clic-vendas"
            style={{
              fontSize: 13,
              color: "var(--muted)",
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            ← Pedidos
          </Link>

          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{
              background: "var(--surface2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "7px 12px",
              fontSize: 13,
            }}
          />

          <button
            onClick={loadLogs}
            disabled={loading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              background: "var(--surface2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 14px",
              fontSize: 13,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            Atualizar
          </button>

          {hasRunning && (
            <span
              style={{
                fontSize: 12,
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Clock size={12} />
              Sync em andamento — atualizando automaticamente...
            </span>
          )}
        </div>

        {/* Summary cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
          {[
            { label: "Syncs totais", value: logs.length, color: "var(--muted)" },
            { label: "Sucesso", value: successCount, color: "var(--success)" },
            { label: "Erro", value: errorCount, color: "var(--error)" },
            { label: "Pedidos buscados", value: totalFetched, color: "var(--accent)" },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: "14px 18px",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", marginBottom: 8 }}>
                {label}
              </div>
              <div style={{ fontSize: 26, fontWeight: 800, color }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Tabela de logs */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 16,
            overflow: "hidden",
          }}
        >
          {/* Header da tabela */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "180px 1fr 100px 80px 80px 80px 100px 40px",
              padding: "10px 20px",
              borderBottom: "1px solid var(--border)",
              background: "var(--surface2)",
              gap: 8,
            }}
          >
            {["Horário", "Status / Trigger", "Buscados", "Salvos", "Erros", "Duração", "Clientes", ""].map((h) => (
              <span
                key={h}
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}
              >
                {h}
              </span>
            ))}
          </div>

          {loading && logs.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhuma sincronização encontrada para {date}.
            </div>
          ) : (
            logs.map((log) => <LogRow key={log.id} log={log} />)
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
