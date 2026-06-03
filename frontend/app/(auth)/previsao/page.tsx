"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Boxes,
  CalendarDays,
  DollarSign,
  Package,
  RefreshCw,
  ShoppingCart,
  TrendingUp,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { previsaoApi } from "@/lib/api";
import type { PrevisaoOverview, PrevisaoPeriodo, PrevisaoProduto } from "@/lib/types";

function fmtNumber(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function fmtBRL(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

function GrowthBadge({ value }: { value: number | null }) {
  if (value === null) {
    return <span style={{ color: "var(--muted)", fontSize: 11 }}>sem comparativo</span>;
  }

  const positive = value >= 0;
  return (
    <span
      style={{
        color: positive ? "var(--success)" : "var(--error)",
        background: positive ? "var(--success)14" : "var(--error)14",
        border: `1px solid ${positive ? "var(--success)" : "var(--error)"}33`,
        borderRadius: 999,
        padding: "2px 8px",
        fontSize: 11,
        fontWeight: 700,
        whiteSpace: "nowrap",
      }}
    >
      {positive ? "+" : ""}
      {value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%
    </span>
  );
}

function StatBlock({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  accent?: boolean;
}) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "16px 18px",
        minHeight: 104,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>
          {label}
        </span>
        <Icon size={17} color={accent ? "var(--accent)" : "var(--muted)"} />
      </div>
      <div style={{ fontSize: 24, fontWeight: 800, color: "var(--text)", marginTop: 10, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function ProductRow({ product, index, showGrowth }: { product: PrevisaoProduto; index: number; showGrowth?: boolean }) {
  return (
    <tr style={{ borderTop: "1px solid var(--border)" }}>
      <td style={{ padding: "10px 14px", color: "var(--muted)", fontSize: 12, width: 48 }}>
        {String(index + 1).padStart(2, "0")}
      </td>
      <td style={{ padding: "10px 14px", minWidth: 260 }}>
        <div style={{ color: "var(--text)", fontWeight: 650, fontSize: 13, lineHeight: 1.35 }}>
          {product.desPro || product.codPro || "Produto sem nome"}
        </div>
        <div style={{ color: "var(--accent)", fontFamily: "monospace", fontSize: 11, marginTop: 2 }}>
          {product.codPro || "sem codigo"}
        </div>
      </td>
      <td style={{ padding: "10px 14px", color: "var(--text)", fontWeight: 700, whiteSpace: "nowrap" }}>
        {fmtNumber(product.total_qtd)}
      </td>
      <td style={{ padding: "10px 14px", color: "var(--muted)", whiteSpace: "nowrap" }}>
        {product.pedidos} pedidos
      </td>
      <td style={{ padding: "10px 14px", color: "var(--text)", fontWeight: 650, whiteSpace: "nowrap" }}>
        {fmtBRL(product.total_valor)}
      </td>
      {showGrowth && (
        <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
          <GrowthBadge value={product.growth_pct} />
        </td>
      )}
    </tr>
  );
}

function PeriodPanel({ period }: { period: PrevisaoPeriodo }) {
  return (
    <section
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 800, color: "var(--text)", textTransform: "capitalize" }}>
            {period.label}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
            {period.orders_count} pedidos, {fmtNumber(period.total_qtd)} unidades
          </div>
        </div>
        <span style={{ fontSize: 12, color: "var(--accent)", fontWeight: 700, whiteSpace: "nowrap" }}>
          {fmtBRL(period.total_valor)}
        </span>
      </div>

      {period.top_products.length === 0 ? (
        <div style={{ padding: 24, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
          Sem itens neste periodo.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>
              {period.top_products.slice(0, 5).map((product, index) => (
                <ProductRow key={`${period.period}-${product.codPro || product.desPro}`} product={product} index={index} showGrowth={period.period > 1} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function PrevisaoPage() {
  const [data, setData] = useState<PrevisaoOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [periodCount, setPeriodCount] = useState<3 | 4>(4);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await previsaoApi.list({ year, periodCount, limit: 12 });
      setData(result);
      if (!year) setYear(result.year);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar previsao");
    } finally {
      setLoading(false);
    }
  }, [year, periodCount]);

  useEffect(() => {
    load();
  }, [load]);

  const strongestPeriod = useMemo(() => {
    if (!data?.periods.length) return null;
    return [...data.periods].sort((a, b) => b.total_qtd - a.total_qtd)[0];
  }, [data]);

  const availableYears = data?.available_years.length
    ? data.available_years
    : [year ?? new Date().getFullYear()];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Previsao" />

      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, color: "var(--text)", letterSpacing: 0, lineHeight: 1.2 }}>
              Produtos com maior saida por periodo
            </h1>
            <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 13, maxWidth: 760, lineHeight: 1.45 }}>
              Ranking calculado a partir dos itens salvos na base de pedidos do Clic Vendas.
            </p>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <select
              value={year ?? ""}
              onChange={(event) => setYear(Number(event.target.value))}
              style={{ background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", fontSize: 13 }}
            >
              {availableYears.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select
              value={periodCount}
              onChange={(event) => setPeriodCount(Number(event.target.value) as 3 | 4)}
              style={{ background: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", fontSize: 13 }}
            >
              <option value={4}>4 periodos</option>
              <option value={3}>3 periodos</option>
            </select>
            <button
              onClick={load}
              disabled={loading}
              title="Atualizar"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "9px 14px",
                fontWeight: 700,
                fontSize: 13,
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.75 : 1,
              }}
            >
              <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
              Atualizar
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: "var(--error)12", border: "1px solid var(--error)44", color: "var(--error)", borderRadius: 8, padding: "10px 12px", marginBottom: 16, fontSize: 13 }}>
            {error}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 12, marginBottom: 18 }}>
          <StatBlock label="Pedidos analisados" value={data ? fmtNumber(data.summary.orders_count) : "-"} icon={ShoppingCart} />
          <StatBlock label="Produtos unicos" value={data ? fmtNumber(data.summary.products_count) : "-"} icon={Package} />
          <StatBlock label="Unidades vendidas" value={data ? fmtNumber(data.summary.total_qtd) : "-"} icon={Boxes} accent />
          <StatBlock label="Valor vendido" value={data ? fmtBRL(data.summary.total_valor) : "-"} icon={DollarSign} accent />
          <StatBlock label="Periodo mais forte" value={strongestPeriod?.label ?? "-"} sub={strongestPeriod ? `${fmtNumber(strongestPeriod.total_qtd)} unidades` : undefined} icon={CalendarDays} />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(320px, 0.9fr)", gap: 16, alignItems: "start" }}>
          <section style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden", minWidth: 0 }}>
            <div style={{ padding: "15px 18px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div>
                <div style={{ fontWeight: 800, color: "var(--text)", fontSize: 14 }}>Previsao de maior saida</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 3 }}>
                  Produtos ordenados por volume total no ano selecionado.
                </div>
              </div>
              <TrendingUp size={18} color="var(--accent)" />
            </div>

            {loading && !data ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
            ) : !data?.forecast_products.length ? (
              <div style={{ padding: 40, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
                Nenhum item de pedido encontrado para este periodo.
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: "var(--surface2)" }}>
                      {["#", "Produto", "Unidades", "Pedidos", "Valor"].map((header) => (
                        <th key={header} style={{ padding: "10px 14px", textAlign: "left", fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.forecast_products.map((product, index) => (
                      <ProductRow key={product.codPro || product.desPro} product={product} index={index} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 800 }}>
              <BarChart3 size={14} />
              Top por periodo
            </div>
            {data?.periods.map((period) => (
              <PeriodPanel key={period.period} period={period} />
            ))}
          </section>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 1100px) {
          div[style*="minmax(0, 1.1fr)"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
