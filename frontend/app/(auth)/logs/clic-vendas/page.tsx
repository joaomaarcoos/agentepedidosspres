"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Clock, Eye, RefreshCw, Search, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { logsApi } from "@/lib/api";
import type { ClicRequestLog, ClicRequestLogsOverview, ClicRequestLogStatus } from "@/lib/types";

const STATUS_OPTIONS: Array<{ value: ClicRequestLogStatus | "all"; label: string }> = [
  { value: "all", label: "Todos os status" },
  { value: "success", label: "Sucesso" },
  { value: "error", label: "Erro" },
  { value: "pending", label: "Pendente" },
];

function fmtDateTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function statusMeta(status: ClicRequestLogStatus) {
  if (status === "success") return { label: "Sucesso", color: "var(--success)", icon: CheckCircle2 };
  if (status === "error") return { label: "Erro", color: "var(--error)", icon: AlertCircle };
  return { label: "Pendente", color: "var(--warn)", icon: Clock };
}

function StatusBadge({ status }: { status: ClicRequestLogStatus }) {
  const meta = statusMeta(status);
  const Icon = meta.icon;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 9px",
        borderRadius: 8,
        fontSize: 12,
        fontWeight: 700,
        color: meta.color,
        border: `1px solid ${meta.color}44`,
        background: `${meta.color}18`,
        whiteSpace: "nowrap",
      }}
    >
      <Icon size={13} />
      {meta.label}
    </span>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const content = useMemo(() => JSON.stringify(value ?? null, null, 2), [value]);
  return (
    <section style={{ minWidth: 0 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
        {title}
      </h3>
      <pre
        style={{
          margin: 0,
          padding: 14,
          minHeight: 180,
          maxHeight: 360,
          overflow: "auto",
          borderRadius: 8,
          border: "1px solid var(--border)",
          background: "#080910",
          color: "var(--text)",
          fontSize: 12,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {content}
      </pre>
    </section>
  );
}

function DetailPanel({ log, onClose }: { log: ClicRequestLog | null; onClose: () => void }) {
  if (!log) return null;
  return (
    <aside
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "min(760px, 100vw)",
        height: "100dvh",
        zIndex: 50,
        background: "var(--surface)",
        borderLeft: "1px solid var(--border)",
        boxShadow: "0 0 40px rgba(0,0,0,0.35)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ padding: 18, borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <StatusBadge status={log.status} />
            <span style={{ color: "var(--muted)", fontSize: 12 }}>{log.method} {log.endpoint}</span>
          </div>
          <h2 style={{ margin: 0, fontSize: 18, color: "var(--text)" }}>
            Requisicao ao Clic Vendas
          </h2>
        </div>
        <button
          onClick={onClose}
          aria-label="Fechar detalhe"
          style={{
            width: 36,
            height: 36,
            display: "grid",
            placeItems: "center",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--surface2)",
            color: "var(--text)",
            cursor: "pointer",
          }}
        >
          <X size={18} />
        </button>
      </div>

      <div style={{ padding: 18, overflow: "auto", display: "grid", gap: 18 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 10,
          }}
        >
          {[
            ["Criado em", fmtDateTime(log.created_at)],
            ["Enviado em", fmtDateTime(log.sent_at)],
            ["Respondido em", fmtDateTime(log.responded_at)],
            ["Duracao", log.duration_ms != null ? `${log.duration_ms} ms` : "-"],
            ["HTTP", log.http_status ?? "-"],
            ["Protocolo", log.protocol || "-"],
            ["Representante", log.representative_document || String(log.cod_rep || "-")],
            ["Cliente", log.customer_document || log.customer_code || "-"],
          ].map(([label, value]) => (
            <div key={String(label)} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10, background: "var(--surface2)" }}>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 5 }}>{label}</div>
              <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 700, overflowWrap: "anywhere" }}>{String(value)}</div>
            </div>
          ))}
        </div>

        {log.error_message && (
          <div style={{ border: "1px solid var(--error)", borderRadius: 8, padding: 12, background: "rgba(248,113,113,0.08)", color: "var(--error)", fontSize: 13 }}>
            {log.error_message}
          </div>
        )}

        <JsonBlock title="Request payload enviado" value={log.request_payload} />
        <JsonBlock title="Response retornado" value={log.response_payload} />
      </div>
    </aside>
  );
}

export default function ClicVendasLogsPage() {
  const [data, setData] = useState<ClicRequestLogsOverview | null>(null);
  const [selected, setSelected] = useState<ClicRequestLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ClicRequestLogStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await logsApi.listClicVendas({
        status,
        search: search || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        page,
        pageSize: 30,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar logs");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, page, search, status]);

  useEffect(() => {
    load();
  }, [load]);

  async function openDetail(row: ClicRequestLog) {
    setDetailLoading(true);
    try {
      const detail = await logsApi.getClicVendas(row.id);
      setSelected(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao abrir log");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <>
      <Header />
      <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 18 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, color: "var(--text)" }}>Logs Clic Vendas</h1>
            <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 13 }}>
              Auditoria das requisicoes montadas pelo sistema e enviadas para o Clic.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              border: "1px solid var(--border)",
              borderRadius: 8,
              background: "var(--surface2)",
              color: "var(--text)",
              padding: "9px 12px",
              cursor: "pointer",
            }}
          >
            <RefreshCw size={15} />
            Atualizar
          </button>
        </div>

        <section style={{ display: "grid", gridTemplateColumns: "minmax(220px, 1fr) 180px 160px 160px auto", gap: 10, marginBottom: 16 }}>
          <label style={{ position: "relative", minWidth: 0 }}>
            <Search size={16} style={{ position: "absolute", left: 12, top: 12, color: "var(--muted)" }} />
            <input
              value={search}
              onChange={(event) => { setSearch(event.target.value); setPage(1); }}
              placeholder="Buscar protocolo, cliente, representante..."
              style={{
                width: "100%",
                height: 40,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--text)",
                padding: "0 12px 0 38px",
              }}
            />
          </label>
          <select
            value={status}
            onChange={(event) => { setStatus(event.target.value as ClicRequestLogStatus | "all"); setPage(1); }}
            style={{ height: 40, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", padding: "0 10px" }}
          >
            {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => { setDateFrom(event.target.value); setPage(1); }}
            style={{ height: 40, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", padding: "0 10px" }}
          />
          <input
            type="date"
            value={dateTo}
            onChange={(event) => { setDateTo(event.target.value); setPage(1); }}
            style={{ height: 40, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", padding: "0 10px" }}
          />
          <button
            onClick={() => { setSearch(""); setStatus("all"); setDateFrom(""); setDateTo(""); setPage(1); }}
            style={{ height: 40, borderRadius: 8, border: "1px solid var(--border)", background: "transparent", color: "var(--muted)", padding: "0 12px", cursor: "pointer" }}
          >
            Limpar
          </button>
        </section>

        {data && (
          <section style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
            {[
              ["Total", data.total],
              ["Sucesso", data.stats.success || 0],
              ["Erro", data.stats.error || 0],
              ["Pendente", data.stats.pending || 0],
            ].map(([label, value]) => (
              <div key={String(label)} style={{ border: "1px solid var(--border)", background: "var(--surface)", borderRadius: 8, padding: "10px 14px", minWidth: 120 }}>
                <div style={{ color: "var(--muted)", fontSize: 11 }}>{label}</div>
                <div style={{ color: "var(--text)", fontSize: 20, fontWeight: 800 }}>{value}</div>
              </div>
            ))}
          </section>
        )}

        {error && (
          <div style={{ border: "1px solid var(--error)", borderRadius: 8, padding: 12, marginBottom: 16, color: "var(--error)", background: "rgba(248,113,113,0.08)" }}>
            {error}
          </div>
        )}

        <section style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", background: "var(--surface)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 980 }}>
            <thead style={{ background: "var(--surface2)", color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.4 }}>
              <tr>
                <th style={{ textAlign: "left", padding: 12 }}>Criado</th>
                <th style={{ textAlign: "left", padding: 12 }}>Status</th>
                <th style={{ textAlign: "left", padding: 12 }}>Endpoint</th>
                <th style={{ textAlign: "left", padding: 12 }}>Representante</th>
                <th style={{ textAlign: "left", padding: 12 }}>Cliente</th>
                <th style={{ textAlign: "left", padding: 12 }}>Resposta</th>
                <th style={{ textAlign: "right", padding: 12 }}>Detalhe</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ padding: 24, color: "var(--muted)" }}>Carregando logs...</td></tr>
              )}
              {!loading && (!data || data.logs.length === 0) && (
                <tr><td colSpan={7} style={{ padding: 24, color: "var(--muted)" }}>Nenhuma requisicao registrada.</td></tr>
              )}
              {!loading && data?.logs.map((log) => (
                <tr key={log.id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: 12, whiteSpace: "nowrap" }}>
                    <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 700 }}>{fmtDateTime(log.created_at)}</div>
                    <div style={{ color: "var(--muted)", fontSize: 11 }}>{log.duration_ms != null ? `${log.duration_ms} ms` : "-"}</div>
                  </td>
                  <td style={{ padding: 12 }}><StatusBadge status={log.status} /></td>
                  <td style={{ padding: 12, color: "var(--text)", fontSize: 13 }}>{log.method} {log.endpoint}</td>
                  <td style={{ padding: 12, color: "var(--muted)", fontSize: 13 }}>{log.representative_document || log.cod_rep || "-"}</td>
                  <td style={{ padding: 12, color: "var(--muted)", fontSize: 13 }}>{log.customer_document || log.customer_code || "-"}</td>
                  <td style={{ padding: 12, color: log.status === "error" ? "var(--error)" : "var(--muted)", fontSize: 12, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {log.error_message || (log.http_status ? `HTTP ${log.http_status}` : "-")}
                  </td>
                  <td style={{ padding: 12, textAlign: "right" }}>
                    <button
                      onClick={() => openDetail(log)}
                      disabled={detailLoading}
                      style={{ display: "inline-flex", alignItems: "center", gap: 6, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface2)", color: "var(--text)", padding: "7px 10px", cursor: "pointer" }}
                    >
                      <Eye size={14} />
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {data && data.pages > 1 && (
          <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, marginTop: 14 }}>
            <button
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1}
              style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", color: "var(--text)", padding: "8px 12px", cursor: "pointer" }}
            >
              Anterior
            </button>
            <span style={{ color: "var(--muted)", fontSize: 13 }}>Pagina {data.page} de {data.pages}</span>
            <button
              onClick={() => setPage((value) => Math.min(data.pages, value + 1))}
              disabled={page >= data.pages}
              style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", color: "var(--text)", padding: "8px 12px", cursor: "pointer" }}
            >
              Proxima
            </button>
          </div>
        )}
      </main>
      <DetailPanel log={selected} onClose={() => setSelected(null)} />
    </>
  );
}
