"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart2, ChevronLeft, ChevronRight, RefreshCw,
  TrendingUp, Send, CheckCircle2, DollarSign,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { resultadosApi } from "@/lib/api";
import type { ResultadosOverview, ResultadosTarget } from "@/lib/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtBRL(value: number | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 0 });
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

// ─── Badges ───────────────────────────────────────────────────────────────────

function PipelineBadge({ type }: { type: "recorrencia" | "ativacao" }) {
  const isRec = type === "recorrencia";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: isRec ? "var(--accent)18" : "var(--warn)18",
      color: isRec ? "var(--accent)" : "var(--warn)",
      border: `1px solid ${isRec ? "var(--accent)" : "var(--warn)"}44`,
      textTransform: "uppercase", whiteSpace: "nowrap",
    }}>
      {isRec ? "Recorrência" : "Ativação"}
    </span>
  );
}

function StatusBadge({ target }: { target: ResultadosTarget }) {
  const converted = target.status === "converted";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: converted ? "var(--success)18" : "var(--muted)22",
      color: converted ? "var(--success)" : "var(--muted)",
      border: `1px solid ${converted ? "var(--success)" : "var(--muted)"}44`,
      whiteSpace: "nowrap",
    }}>
      {converted ? "Convertido" : "Aguardando"}
    </span>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, icon: Icon, accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent?: boolean;
}) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12,
      padding: "18px 22px", display: "flex", alignItems: "flex-start", gap: 14,
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 9,
        background: accent ? "var(--accent)20" : "var(--border)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: accent ? "var(--accent)" : "var(--muted)", flexShrink: 0,
      }}>
        <Icon size={18} />
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text)", lineHeight: 1.1 }}>
          {value}
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 3 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

// ─── Pipeline breakdown ───────────────────────────────────────────────────────

function PipelineRow({ label, dispatched, converted, revenue, color }: {
  label: string; dispatched: number; converted: number;
  revenue: number; color: string;
}) {
  const total = dispatched + converted;
  const rate = total > 0 ? Math.round(converted / total * 100) : 0;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16,
      padding: "12px 16px", borderRadius: 10, background: `${color}08`,
      border: `1px solid ${color}22`,
    }}>
      <span style={{
        fontSize: 11, fontWeight: 700, color, textTransform: "uppercase",
        minWidth: 90,
      }}>{label}</span>
      <div style={{ flex: 1, display: "flex", gap: 24, fontSize: 13 }}>
        <span style={{ color: "var(--muted)" }}>Disparados: <strong style={{ color: "var(--text)" }}>{dispatched + converted}</strong></span>
        <span style={{ color: "var(--muted)" }}>Convertidos: <strong style={{ color: "var(--success)" }}>{converted}</strong></span>
        <span style={{ color: "var(--muted)" }}>Taxa: <strong style={{ color }}>{rate}%</strong></span>
        <span style={{ color: "var(--muted)" }}>Receita: <strong style={{ color: "var(--text)" }}>{fmtBRL(revenue)}</strong></span>
      </div>
    </div>
  );
}

// ─── Filtro de pipeline ───────────────────────────────────────────────────────

type FilterType = "all" | "recorrencia" | "ativacao";

const FILTER_TABS: { key: FilterType; label: string }[] = [
  { key: "all", label: "Todos" },
  { key: "recorrencia", label: "Recorrência" },
  { key: "ativacao", label: "Ativação" },
];

// ─── Página principal ─────────────────────────────────────────────────────────

export default function ResultadosPage() {
  const [data, setData] = useState<ResultadosOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await resultadosApi.list({ targetType: filter, page, pageSize });
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filter, page, pageSize]);

  useEffect(() => { load(); }, [load]);

  // Resetar página ao mudar filtro
  const handleFilter = (f: FilterType) => {
    setFilter(f);
    setPage(1);
  };

  const stats = data?.stats;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <Header title="Resultados" subtitle="Impacto dos disparos da IA" />

      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>

        {/* Stats cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
          <StatCard
            label="Total Disparados"
            value={(stats ? stats.dispatched_total + stats.converted_total : 0)}
            icon={Send}
          />
          <StatCard
            label="Convertidos"
            value={stats?.converted_total ?? 0}
            sub="pedidos fechados pela IA"
            icon={CheckCircle2}
            accent
          />
          <StatCard
            label="Taxa de Conversão"
            value={`${stats?.conversion_rate ?? 0}%`}
            icon={TrendingUp}
            accent={!!stats && stats.conversion_rate > 0}
          />
          <StatCard
            label="Receita Gerada"
            value={fmtBRL(stats?.revenue_total)}
            sub="pedidos convertidos"
            icon={DollarSign}
            accent={!!stats && stats.revenue_total > 0}
          />
        </div>

        {/* Breakdown por pipeline */}
        {stats && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
            <PipelineRow
              label="Recorrência"
              dispatched={stats.by_pipeline.recorrencia.dispatched}
              converted={stats.by_pipeline.recorrencia.converted}
              revenue={stats.by_pipeline.recorrencia.revenue}
              color="var(--accent)"
            />
            <PipelineRow
              label="Ativação"
              dispatched={stats.by_pipeline.ativacao.dispatched}
              converted={stats.by_pipeline.ativacao.converted}
              revenue={stats.by_pipeline.ativacao.revenue}
              color="var(--warn)"
            />
          </div>
        )}

        {/* Filtros + refresh */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {FILTER_TABS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => handleFilter(key)}
                style={{
                  padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)",
                  background: filter === key ? "var(--accent)" : "var(--surface)",
                  color: filter === key ? "#fff" : "var(--muted)",
                  fontSize: 12, fontWeight: 600, cursor: "pointer",
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={load}
            disabled={loading}
            title="Atualizar"
            style={{
              padding: "6px 12px", borderRadius: 8,
              border: "1px solid var(--border)", background: "var(--surface)",
              color: "var(--muted)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
              fontSize: 12,
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            Atualizar
          </button>
        </div>

        {/* Tabela */}
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 12, overflow: "hidden",
        }}>
          {loading && !data ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Carregando...
            </div>
          ) : !data?.targets.length ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              <BarChart2 size={32} style={{ marginBottom: 12, opacity: 0.4 }} />
              <div>Nenhum disparo encontrado ainda.</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Os resultados aparecerão aqui conforme a IA fechar pedidos.</div>
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Cliente", "Pipeline", "Disparo", "Pedido", "Valor", "Status"].map(h => (
                    <th key={h} style={{
                      padding: "10px 14px", textAlign: "left",
                      fontSize: 11, fontWeight: 700, color: "var(--muted)",
                      textTransform: "uppercase", letterSpacing: "0.04em",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data.targets as ResultadosTarget[]).map((t, i) => (
                  <tr
                    key={t.id}
                    style={{
                      borderBottom: i < data.targets.length - 1 ? "1px solid var(--border)" : undefined,
                      background: t.status === "converted" ? "var(--success)05" : undefined,
                    }}
                  >
                    <td style={{ padding: "11px 14px" }}>
                      <div style={{ fontWeight: 600, color: "var(--text)" }}>
                        {t.customer_name ?? "—"}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>
                        {t.customer_phone ?? t.cpf_cnpj}
                      </div>
                    </td>
                    <td style={{ padding: "11px 14px" }}>
                      <PipelineBadge type={t.target_type} />
                    </td>
                    <td style={{ padding: "11px 14px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                      {fmtDate(t.dispatched_at)}
                    </td>
                    <td style={{ padding: "11px 14px" }}>
                      {t.converted_order_num ? (
                        <span style={{ fontWeight: 700, color: "var(--success)" }}>
                          #{t.converted_order_num}
                        </span>
                      ) : (
                        <span style={{ color: "var(--muted)" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "11px 14px", fontWeight: 600, color: "var(--text)", whiteSpace: "nowrap" }}>
                      {fmtBRL(t.converted_order_value)}
                    </td>
                    <td style={{ padding: "11px 14px" }}>
                      <StatusBadge target={t} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Paginação */}
        {data && data.pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginTop: 16 }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{
                padding: "6px 12px", borderRadius: 8, border: "1px solid var(--border)",
                background: "var(--surface)", color: "var(--muted)",
                cursor: page === 1 ? "default" : "pointer", opacity: page === 1 ? 0.4 : 1,
                display: "flex", alignItems: "center", gap: 4,
              }}
            >
              <ChevronLeft size={14} /> Anterior
            </button>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              Página {page} de {data.pages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              style={{
                padding: "6px 12px", borderRadius: 8, border: "1px solid var(--border)",
                background: "var(--surface)", color: "var(--muted)",
                cursor: page === data.pages ? "default" : "pointer",
                opacity: page === data.pages ? 0.4 : 1,
                display: "flex", alignItems: "center", gap: 4,
              }}
            >
              Próximo <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
