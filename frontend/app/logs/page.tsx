"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronLeft,
  ChevronRight, ChevronUp, Clock, RefreshCw, Send, XCircle,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { logsApi } from "@/lib/api";
import type { DisparoLog, DisparoLogStatus, DisparoLogsOverview } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

// ─── Badges ───────────────────────────────────────────────────────────────────

const STATUS_META: Record<DisparoLogStatus, { label: string; color: string; icon: React.ElementType }> = {
  success:  { label: "Sucesso",   color: "var(--success)", icon: CheckCircle2 },
  partial:  { label: "Parcial",   color: "var(--warn)",    icon: AlertTriangle },
  error:    { label: "Erro",      color: "var(--error)",   icon: XCircle },
  dry_run:  { label: "Dry-run",   color: "var(--muted)",   icon: Clock },
};

function StatusBadge({ status }: { status: DisparoLogStatus }) {
  const { label, color, icon: Icon } = STATUS_META[status] ?? STATUS_META.error;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 9px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}44`,
    }}>
      <Icon size={11} />
      {label}
    </span>
  );
}

function FlowBadge({ flow }: { flow: "recorrencia" | "ativacao" }) {
  const color = flow === "recorrencia" ? "var(--accent)" : "var(--warn)";
  const label = flow === "recorrencia" ? "Recorrência" : "Ativação";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 6, fontSize: 11, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}33`,
    }}>
      {label}
    </span>
  );
}

// ─── Painel de erros expandido ────────────────────────────────────────────────

function ErrorsPanel({ log }: { log: DisparoLog }) {
  if (!log.errors_json?.length) {
    return (
      <div style={{ padding: "14px 20px", color: "var(--muted)", fontSize: 12 }}>
        Nenhum erro registrado.
      </div>
    );
  }
  return (
    <div style={{ padding: "0 0 4px" }}>
      {log.errors_json.map((err, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "1fr auto",
          padding: "12px 20px", borderTop: "1px solid var(--border)",
          gap: 8,
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text)", marginBottom: 4 }}>
              {err.nome || err.id}
            </div>
            <code style={{
              display: "block", fontSize: 12, color: "var(--error)",
              background: "var(--error)0d", borderRadius: 6,
              padding: "6px 10px", fontFamily: "monospace",
              whiteSpace: "pre-wrap", wordBreak: "break-all",
            }}>
              {err.error}
            </code>
          </div>
          <span style={{ fontSize: 10, color: "var(--muted)", whiteSpace: "nowrap", paddingTop: 2 }}>
            #{i + 1}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Linha da tabela com expand ───────────────────────────────────────────────

function LogRow({ log }: { log: DisparoLog }) {
  const [expanded, setExpanded] = useState(false);
  const hasErrors = (log.errors_count ?? 0) > 0;

  return (
    <>
      <tr
        onClick={() => setExpanded(v => !v)}
        style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
        onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
        onMouseLeave={e => (e.currentTarget.style.background = "")}
      >
        {/* Data/hora */}
        <td style={{ padding: "12px 16px", whiteSpace: "nowrap" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
            {fmtDateTime(log.started_at)}
          </div>
          {log.finished_at && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
              Duração: {fmtDuration(log.duration_ms)}
            </div>
          )}
        </td>

        {/* Flow */}
        <td style={{ padding: "12px 16px" }}>
          <FlowBadge flow={log.flow} />
        </td>

        {/* Status */}
        <td style={{ padding: "12px 16px" }}>
          <StatusBadge status={log.status} />
        </td>

        {/* Métricas */}
        <td style={{ padding: "12px 16px" }}>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Processados: <strong style={{ color: "var(--text)" }}>{log.processed}</strong>
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Enviados: <strong style={{ color: "var(--success)" }}>{log.dispatched}</strong>
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Pulados: <strong style={{ color: "var(--muted)" }}>{log.skipped}</strong>
            </span>
            {hasErrors && (
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Erros: <strong style={{ color: "var(--error)" }}>{log.errors_count}</strong>
              </span>
            )}
          </div>
        </td>

        {/* Origem */}
        <td style={{ padding: "12px 16px" }}>
          <span style={{ fontSize: 12, color: "var(--muted)", textTransform: "capitalize" }}>
            {log.triggered_by}
          </span>
          {log.dry_run && (
            <span style={{
              marginLeft: 6, fontSize: 10, fontWeight: 700,
              color: "var(--muted)", background: "var(--surface2)",
              padding: "1px 5px", borderRadius: 4, border: "1px solid var(--border)",
            }}>
              DRY
            </span>
          )}
        </td>

        {/* Expand toggle */}
        <td style={{ padding: "12px 16px", textAlign: "right" }}>
          {hasErrors ? (
            <button
              onClick={e => { e.stopPropagation(); setExpanded(v => !v); }}
              style={{
                display: "inline-flex", alignItems: "center", gap: 5,
                background: "var(--error)12", color: "var(--error)",
                border: "1px solid var(--error)33", borderRadius: 6,
                padding: "4px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer",
              }}
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {log.errors_count} erro{log.errors_count !== 1 ? "s" : ""}
            </button>
          ) : (
            <span style={{ color: "var(--muted)", fontSize: 11 }}>
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </span>
          )}
        </td>
      </tr>

      {expanded && (
        <tr style={{ background: "var(--surface2)" }}>
          <td colSpan={6} style={{ padding: 0 }}>
            <ErrorsPanel log={log} />
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Filtros ──────────────────────────────────────────────────────────────────

const FLOW_OPTS = [
  { value: "", label: "Todos os fluxos" },
  { value: "recorrencia", label: "Recorrência" },
  { value: "ativacao", label: "Ativação" },
];

const STATUS_OPTS = [
  { value: "", label: "Todos os status" },
  { value: "success", label: "Sucesso" },
  { value: "partial", label: "Parcial" },
  { value: "error", label: "Erro" },
  { value: "dry_run", label: "Dry-run" },
];

// ─── Página principal ─────────────────────────────────────────────────────────

export default function LogsPage() {
  const [data, setData] = useState<DisparoLogsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [flowFilter, setFlowFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (p = 1, flow = flowFilter, status = statusFilter) => {
    setLoading(true);
    setError(null);
    try {
      const result = await logsApi.listDisparo({
        flow: flow || undefined,
        status: status || undefined,
        page: p,
        pageSize: 30,
      });
      setData(result);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar logs");
    } finally {
      setLoading(false);
    }
  }, [flowFilter, statusFilter]);

  useEffect(() => { load(1, flowFilter, statusFilter); }, [flowFilter, statusFilter]);

  // Resumo rápido para os cards de topo
  const totals = data?.logs.reduce(
    (acc, log) => {
      acc.dispatched += log.dispatched;
      acc.errors += log.errors_count;
      if (log.status === "error") acc.failed_runs++;
      return acc;
    },
    { dispatched: 0, errors: 0, failed_runs: 0 }
  );

  const selectStyle: React.CSSProperties = {
    padding: "7px 12px", borderRadius: 8, fontSize: 12, fontWeight: 500,
    background: "var(--surface2)", border: "1px solid var(--border)",
    color: "var(--text)", cursor: "pointer", outline: "none",
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Logs de Disparos" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>

        {/* Barra de controles */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
          <select value={flowFilter} onChange={e => { setFlowFilter(e.target.value); setPage(1); }} style={selectStyle}>
            {FLOW_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }} style={selectStyle}>
            {STATUS_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <button
            onClick={() => load(1, flowFilter, statusFilter)}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "transparent", color: "var(--muted)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 12px", fontSize: 13, cursor: "pointer",
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
          </button>

          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>
            {data?.total ?? 0} execuções registradas
          </span>
        </div>

        {/* Cards de resumo */}
        {data && data.logs.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 14, marginBottom: 24 }}>
            {[
              { label: "Mensagens Enviadas",  value: totals?.dispatched ?? 0, icon: Send,         color: "var(--success)" },
              { label: "Erros de Envio",       value: totals?.errors ?? 0,    icon: XCircle,      color: "var(--error)"   },
              { label: "Execuções com Falha",  value: totals?.failed_runs ?? 0, icon: AlertTriangle, color: "var(--warn)"  },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 12, padding: "16px 20px",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                    {label}
                  </span>
                  <Icon size={15} color={color} />
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: "var(--text)" }}>{value}</div>
                <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 4 }}>nesta página</div>
              </div>
            ))}
          </div>
        )}

        {/* Tabela */}
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 16, overflow: "hidden",
        }}>
          <div style={{
            padding: "14px 20px", borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
              Histórico de Execuções
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Clique em uma linha para expandir erros
            </span>
          </div>

          {error && (
            <div style={{ padding: 32, textAlign: "center", color: "var(--error)", fontSize: 13 }}>
              {error}
            </div>
          )}

          {loading && !error && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Carregando...
            </div>
          )}

          {!loading && !error && (!data || data.logs.length === 0) && (
            <div style={{ padding: 48, textAlign: "center" }}>
              <Send size={32} color="var(--border)" style={{ marginBottom: 12 }} />
              <div style={{ fontSize: 14, color: "var(--muted)", fontWeight: 600 }}>
                Nenhum disparo registrado ainda
              </div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
                Os logs aparecerão aqui após o primeiro disparo ser executado.
              </div>
            </div>
          )}

          {!loading && !error && data && data.logs.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Data / Hora", "Fluxo", "Status", "Métricas", "Origem", ""].map(h => (
                      <th key={h} style={{
                        padding: "10px 16px", textAlign: "left",
                        fontSize: 11, fontWeight: 700, color: "var(--muted)",
                        textTransform: "uppercase", letterSpacing: 0.5, whiteSpace: "nowrap",
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.logs.map(log => <LogRow key={log.id} log={log} />)}
                </tbody>
              </table>
            </div>
          )}

          {/* Paginação */}
          {data && data.pages > 1 && (
            <div style={{
              padding: "12px 20px", borderTop: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Página {page} de {data.pages} · {data.total} registros
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => load(page - 1)}
                  disabled={page <= 1}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "6px 12px", borderRadius: 6, fontSize: 12,
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    cursor: page <= 1 ? "not-allowed" : "pointer", opacity: page <= 1 ? 0.5 : 1,
                    color: "var(--text)",
                  }}
                >
                  <ChevronLeft size={14} /> Anterior
                </button>
                <button
                  onClick={() => load(page + 1)}
                  disabled={page >= data.pages}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "6px 12px", borderRadius: 6, fontSize: 12,
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    cursor: page >= data.pages ? "not-allowed" : "pointer",
                    opacity: page >= data.pages ? 0.5 : 1,
                    color: "var(--text)",
                  }}
                >
                  Próxima <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
