"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle, Bot, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight,
  CircleDollarSign, Clock3, PackageSearch, RefreshCw, Search, Send, Users,
  Wifi, WifiOff,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { secretariaApi } from "@/lib/api";
import type { SecretaryDashboard, SecretaryOrder, SecretaryOrderStatus } from "@/lib/types";

const STATUS_OPTIONS: Array<{ value: SecretaryOrderStatus | "all"; label: string }> = [
  { value: "all", label: "Todos os status" },
  { value: "draft", label: "Rascunho" },
  { value: "awaiting_confirmation", label: "Aguardando confirmação" },
  { value: "submitting", label: "Enviando" },
  { value: "submitted", label: "Enviado" },
  { value: "synced", label: "Sincronizado" },
  { value: "failed", label: "Com erro" },
  { value: "cancelled", label: "Cancelado" },
];

const STATUS_META: Record<SecretaryOrderStatus, { label: string; color: string; background: string }> = {
  draft: { label: "Rascunho", color: "#94a3b8", background: "rgba(148,163,184,.12)" },
  awaiting_confirmation: { label: "Aguardando confirmação", color: "#f59e0b", background: "rgba(245,158,11,.12)" },
  submitting: { label: "Enviando", color: "#38bdf8", background: "rgba(56,189,248,.12)" },
  submitted: { label: "Enviado", color: "#60a5fa", background: "rgba(96,165,250,.12)" },
  synced: { label: "Sincronizado", color: "#22c55e", background: "rgba(34,197,94,.12)" },
  failed: { label: "Com erro", color: "#ef4444", background: "rgba(239,68,68,.12)" },
  cancelled: { label: "Cancelado", color: "#64748b", background: "rgba(100,116,139,.12)" },
};

const PIPELINE: SecretaryOrderStatus[] = [
  "draft", "awaiting_confirmation", "submitting", "submitted", "synced", "failed",
];

function dateInput(daysAgo = 0) {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

function money(value: number | null | undefined) {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function compactNumber(value: number) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value || 0);
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function StatusBadge({ status }: { status: SecretaryOrderStatus }) {
  const meta = STATUS_META[status] || STATUS_META.draft;
  return (
    <span className="status-badge" style={{ color: meta.color, background: meta.background }}>
      <span style={{ background: meta.color }} />{meta.label}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, note, accent }: {
  icon: React.ElementType; label: string; value: string | number; note: string; accent?: boolean;
}) {
  return (
    <article className={`metric-card${accent ? " metric-accent" : ""}`}>
      <div className="metric-heading"><span>{label}</span><Icon size={16} /></div>
      <strong>{value}</strong><small>{note}</small>
    </article>
  );
}

function OrderDetails({ order }: { order: SecretaryOrder }) {
  return (
    <div className="order-details">
      <div>
        <span className="detail-label">Itens confirmados</span>
        {(order.items_json || []).map((item, index) => (
          <div className="item-row" key={`${item.cod_produto}-${index}`}>
            <div>
              <strong>{item.nome || "Produto"}</strong>
              <span>Cód. {item.cod_produto || "—"}{item.derivacao ? ` · ${item.derivacao}` : ""}</span>
            </div>
            <div className="item-values">
              <span>{compactNumber(Number(item.quantidade || 0))} {item.unidade || "un"}</span>
              <strong>{money(item.subtotal || 0)}</strong>
            </div>
          </div>
        ))}
        {!order.items_json?.length && <span className="empty-copy">Nenhum item registrado.</span>}
      </div>
      <div className="order-timeline">
        <span className="detail-label">Rastreabilidade</span>
        <p>Protocolo interno: <strong>{order.protocol}</strong></p>
        <p>Pedido ClicVendas: <strong>{order.clic_order_number || "Ainda não atribuído"}</strong></p>
        <p>Confirmado: <strong>{formatDate(order.confirmed_at)}</strong></p>
        <p>Sincronizado: <strong>{formatDate(order.synced_at)}</strong></p>
        {order.error_message && <div className="error-detail"><AlertCircle size={15} />{order.error_message}</div>}
      </div>
    </div>
  );
}

export default function IaSecretariaPage() {
  const [data, setData] = useState<SecretaryDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dateFrom, setDateFrom] = useState(dateInput(29));
  const [dateTo, setDateTo] = useState(dateInput());
  const [status, setStatus] = useState<SecretaryOrderStatus | "all">("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await secretariaApi.dashboard({
        dateFrom, dateTo, status, search, page, pageSize: 20,
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Não foi possível carregar o módulo.");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, page, search, status]);

  useEffect(() => { load(); }, [load]);

  const maxDailyValue = useMemo(
    () => Math.max(...(data?.metrics.daily || []).map((day) => day.value), 1),
    [data]
  );
  const connectedInstances = (data?.secretary_instances || []).filter((instance) => instance.status === "open").length;
  const enabledInstances = (data?.secretary_instances || []).filter((instance) => instance.agent_enabled !== false).length;
  const metrics = data?.metrics;

  function applySearch(event: React.FormEvent) {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  }

  return (
    <div className="secretary-shell">
      <Header title="IA Secretária" />
      <main className="secretary-content">
        <section className="module-intro">
          <div>
            <span className="eyebrow"><Bot size={14} /> MARCELA SECRETÁRIA</span>
            <h1>Operação de pedidos dos representantes</h1>
            <p>Acompanhe o atendimento no WhatsApp, o envio ao ClicVendas e a sincronização dos pedidos.</p>
          </div>
          <div className="instance-summary">
            <div className="instance-icon">{connectedInstances ? <Wifi size={20} /> : <WifiOff size={20} />}</div>
            <div>
              <strong>{connectedInstances} de {data?.secretary_instances?.length || 0} conectada(s)</strong>
              <span>{enabledInstances} agente(s) ativo(s)</span>
            </div>
          </div>
        </section>

        <section className="filter-bar">
          <div className="date-filter">
            <label>De<input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} /></label>
            <label>Até<input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} /></label>
          </div>
          <select value={status} onChange={(e) => { setStatus(e.target.value as SecretaryOrderStatus | "all"); setPage(1); }}>
            {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <form className="search-form" onSubmit={applySearch}>
            <Search size={15} />
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Cliente, protocolo, pedido ou representante" />
          </form>
          <button className="refresh-button" onClick={load} disabled={loading}>
            <RefreshCw size={15} className={loading ? "is-spinning" : ""} />Atualizar
          </button>
        </section>

        {error && <div className="load-error"><AlertCircle size={17} />{error}</div>}

        {data?.can_view_results && (
          <>
            <div className="results-heading">
              <div>
                <span className="section-kicker">DASHBOARD DE RESULTADOS</span>
                <h2>Receita gerada pela IA Secretária</h2>
              </div>
              <span>Visível somente para gestor, admin e master</span>
            </div>
            <section className="metrics-grid">
              <MetricCard icon={Clock3} label="Pedidos iniciados" value={metrics?.orders_started || 0} note={`${metrics?.orders_confirmed || 0} confirmados`} />
              <MetricCard icon={Send} label="Enviados ao Clic" value={metrics?.orders_sent || 0} note={`${metrics?.orders_failed || 0} com erro`} accent />
              <MetricCard icon={CheckCircle2} label="Sincronizados" value={metrics?.orders_synced || 0} note="status atualizado no ClicVendas" />
              <MetricCard icon={CircleDollarSign} label="Receita enviada" value={money(metrics?.total_value)} note={`Ticket médio ${money(metrics?.average_ticket)}`} accent />
              <MetricCard icon={Users} label="Representantes" value={metrics?.representatives || 0} note={`${metrics?.customers || 0} clientes atendidos`} />
            </section>
          </>
        )}

        <section className="pipeline-panel">
          <div className="section-heading">
            <div><span className="section-kicker">FLUXO DO PEDIDO</span><h2>Da conversa à sincronização</h2></div>
            <span>{metrics?.orders_started || 0} pedidos no período</span>
          </div>
          <div className="pipeline-grid">
            {PIPELINE.map((key) => {
              const meta = STATUS_META[key];
              const count = metrics?.status_breakdown[key] || 0;
              const width = metrics?.orders_started ? Math.max((count / metrics.orders_started) * 100, count ? 8 : 0) : 0;
              return (
                <div className="pipeline-step" key={key}>
                  <div className="pipeline-title"><span style={{ color: meta.color }}>{meta.label}</span><strong>{count}</strong></div>
                  <div className="pipeline-track"><span style={{ width: `${width}%`, background: meta.color }} /></div>
                </div>
              );
            })}
          </div>
        </section>

        <div className="workspace-grid">
          <section className="orders-panel">
            <div className="section-heading table-heading">
              <div><span className="section-kicker">RASTREABILIDADE</span><h2>Pedidos da Secretária</h2></div>
              <span>{data?.total || 0} registro(s)</span>
            </div>
            <div className="orders-table">
              <div className="order-row order-header">
                <span>Pedido</span><span>Cliente</span><span>Representante</span><span>Valor</span><span>Status</span><span />
              </div>
              {(data?.orders || []).map((order) => (
                <div className="order-entry" key={order.id}>
                  <button className="order-row" onClick={() => setExpanded(expanded === order.id ? null : order.id)}>
                    <span className="order-id"><strong>{order.protocol}</strong><small>{formatDate(order.created_at)}</small></span>
                    <span><strong>{order.customer_name || "Cliente não informado"}</strong><small>Cód. {order.customer_code || "—"}</small></span>
                    <span><strong>Rep. {order.cod_rep}</strong><small>{order.instance_name}</small></span>
                    <span className="order-total">{money(order.total)}</span>
                    <span><StatusBadge status={order.status} /></span>
                    <ChevronDown size={16} className={expanded === order.id ? "expanded" : ""} />
                  </button>
                  {expanded === order.id && <OrderDetails order={order} />}
                </div>
              ))}
              {!loading && !data?.orders.length && <div className="empty-state"><PackageSearch size={24} />Nenhum pedido encontrado com os filtros atuais.</div>}
              {loading && !data && <div className="empty-state">Carregando operação...</div>}
            </div>
            <div className="pagination">
              <span>Página {data?.page || 1} de {data?.pages || 1}</span>
              <div>
                <button disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}><ChevronLeft size={15} /></button>
                <button disabled={page >= (data?.pages || 1) || loading} onClick={() => setPage((current) => current + 1)}><ChevronRight size={15} /></button>
              </div>
            </div>
          </section>

          {data?.can_view_results && <aside className="insights-column">
            <section className="insight-panel">
              <div className="section-heading compact"><h2>Valor por dia</h2><span>Pedidos enviados</span></div>
              <div className="daily-chart">
                {(metrics?.daily || []).slice(-14).map((day) => (
                  <div className="daily-bar" key={day.date} title={`${day.date}: ${money(day.value)}`}>
                    <span style={{ height: `${Math.max((day.value / maxDailyValue) * 100, day.value ? 6 : 2)}%` }} />
                    <small>{day.date.slice(8)}</small>
                  </div>
                ))}
                {!metrics?.daily.length && <span className="empty-copy">Sem movimentação no período.</span>}
              </div>
            </section>
            <section className="insight-panel">
              <div className="section-heading compact"><h2>Principais produtos</h2><span>Por valor</span></div>
              <div className="ranking-list">
                {(metrics?.products || []).slice(0, 5).map((product, index) => (
                  <div className="ranking-row" key={`${product.code}-${index}`}>
                    <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                    <div><strong>{product.name || "Produto"}</strong><small>Cód. {product.code || "—"} · {compactNumber(product.quantity)} un.</small></div>
                    <strong>{money(product.value)}</strong>
                  </div>
                ))}
                {!metrics?.products.length && <span className="empty-copy">Produtos aparecerão após os primeiros pedidos.</span>}
              </div>
            </section>
            <section className="insight-panel">
              <div className="section-heading compact"><h2>Representantes</h2><span>Resultado enviado</span></div>
              <div className="ranking-list">
                {(metrics?.representative_totals || []).slice(0, 5).map((rep) => (
                  <div className="ranking-row" key={rep.cod_rep}>
                    <span className="rep-avatar">{rep.name.slice(0, 1).toUpperCase()}</span>
                    <div><strong>{rep.name}</strong><small>Cód. {rep.cod_rep} · {rep.orders} pedido(s)</small></div>
                    <strong>{money(rep.value)}</strong>
                  </div>
                ))}
                {!metrics?.representative_totals.length && <span className="empty-copy">Nenhum representante no período.</span>}
              </div>
            </section>
          </aside>}
        </div>
      </main>

      <style jsx>{`
        .secretary-shell{flex:1;display:flex;flex-direction:column;overflow:hidden;background:var(--background)}
        .secretary-content{flex:1;overflow:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
        .module-intro{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:4px 2px 8px}
        .eyebrow,.section-kicker{display:flex;align-items:center;gap:7px;color:var(--accent);font-size:10px;font-weight:800;letter-spacing:.14em}
        h1{font-size:24px;line-height:1.15;margin:7px 0 5px;color:var(--text);letter-spacing:-.025em}.module-intro p{margin:0;color:var(--muted);font-size:13px}
        .instance-summary{display:flex;align-items:center;gap:11px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:11px 14px;min-width:230px}
        .instance-icon{width:36px;height:36px;border-radius:8px;background:rgba(34,197,94,.1);color:#22c55e;display:grid;place-items:center}
        .instance-summary strong,.instance-summary span{display:block}.instance-summary strong{font-size:12px;color:var(--text)}.instance-summary span{font-size:11px;color:var(--muted);margin-top:3px}
        .filter-bar{display:flex;align-items:flex-end;gap:9px;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:11px}
        .date-filter{display:flex;gap:8px}.filter-bar label{font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
        .filter-bar input,.filter-bar select{display:block;height:34px;margin-top:4px;border:1px solid var(--border);background:var(--background);color:var(--text);border-radius:7px;padding:0 10px;font-size:12px}
        .filter-bar select{margin-top:0;min-width:170px}.search-form{height:34px;flex:1;display:flex;align-items:center;gap:8px;border:1px solid var(--border);background:var(--background);border-radius:7px;padding:0 10px;color:var(--muted)}
        .search-form input{border:0;background:transparent;margin:0;padding:0;width:100%;outline:0}.refresh-button{height:34px;display:flex;align-items:center;gap:7px;border:1px solid var(--border);background:var(--background);color:var(--text);border-radius:7px;padding:0 12px;font-size:12px;font-weight:700;cursor:pointer}
        .refresh-button:disabled{opacity:.6}.is-spinning{animation:spin 1s linear infinite}.load-error{display:flex;align-items:center;gap:8px;padding:10px 12px;border:1px solid rgba(239,68,68,.3);background:rgba(239,68,68,.08);color:#ef4444;border-radius:8px;font-size:12px}
        .results-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;padding:4px 2px 0}.results-heading h2{margin:4px 0 0;color:var(--text);font-size:16px}.results-heading>span{font-size:10px;color:var(--muted)}
        .metrics-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.metric-card{padding:15px 16px;background:var(--surface);border:1px solid var(--border);border-radius:10px;min-width:0}.metric-card.metric-accent{border-color:rgba(59,130,246,.35)}
        .metric-heading{display:flex;align-items:center;justify-content:space-between;color:var(--muted);font-size:11px}.metric-card strong{display:block;margin-top:10px;font-size:21px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.metric-card small{display:block;color:var(--muted);font-size:10px;margin-top:4px}
        .pipeline-panel,.orders-panel,.insight-panel{background:var(--surface);border:1px solid var(--border);border-radius:11px}.pipeline-panel{padding:16px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.section-heading h2{font-size:14px;color:var(--text);margin:3px 0 0}.section-heading>span{font-size:10px;color:var(--muted)}
        .pipeline-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}.pipeline-title{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;font-weight:700}.pipeline-title strong{color:var(--text);font-size:14px}.pipeline-track{height:3px;margin-top:9px;background:var(--border);border-radius:3px;overflow:hidden}.pipeline-track span{display:block;height:100%;border-radius:3px}
        .workspace-grid{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:16px;align-items:start}.orders-panel{overflow:hidden}.table-heading{padding:16px 16px 0}.orders-table{border-top:1px solid var(--border)}
        .order-row{width:100%;display:grid;grid-template-columns:1.15fr 1.45fr .9fr .7fr 1fr 20px;align-items:center;gap:12px;padding:12px 16px;text-align:left;border:0;background:transparent;color:var(--text)}button.order-row{cursor:pointer;border-top:1px solid var(--border)}.order-entry:first-of-type button.order-row{border-top:0}
        .order-header{color:var(--muted);font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding-top:9px;padding-bottom:9px}.order-row strong,.order-row small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.order-row strong{font-size:11px}.order-row small{font-size:9px;color:var(--muted);margin-top:3px}.order-id strong{font-family:monospace;color:var(--accent)}.order-total{font-size:12px;font-weight:800}.expanded{transform:rotate(180deg)}
        .status-badge{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 7px;font-size:9px;font-weight:800;white-space:nowrap}.status-badge span{width:5px;height:5px;border-radius:50%}
        .order-details{display:grid;grid-template-columns:1.4fr 1fr;gap:22px;background:var(--background);padding:16px 22px;border-top:1px solid var(--border)}.detail-label{display:block;font-size:9px;font-weight:800;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin-bottom:8px}
        .item-row{display:flex;justify-content:space-between;gap:14px;padding:8px 0;border-top:1px solid var(--border)}.item-row:first-child{border-top:0}.item-row strong,.item-row span{display:block;font-size:10px}.item-row span{color:var(--muted);margin-top:3px}.item-values{text-align:right;white-space:nowrap}.order-timeline p{font-size:10px;color:var(--muted);margin:7px 0}.order-timeline p strong{color:var(--text)}.error-detail{display:flex;gap:7px;margin-top:10px;padding:8px;border-radius:7px;background:rgba(239,68,68,.08);color:#ef4444;font-size:10px}
        .empty-state{display:flex;align-items:center;justify-content:center;gap:8px;padding:42px;color:var(--muted);font-size:12px}.empty-copy{display:block;color:var(--muted);font-size:10px;padding:12px 0}.pagination{display:flex;align-items:center;justify-content:space-between;padding:11px 16px;border-top:1px solid var(--border);font-size:10px;color:var(--muted)}.pagination div{display:flex;gap:5px}.pagination button{width:29px;height:27px;display:grid;place-items:center;border:1px solid var(--border);background:var(--background);color:var(--text);border-radius:6px;cursor:pointer}.pagination button:disabled{opacity:.35}
        .insights-column{display:flex;flex-direction:column;gap:12px}.insight-panel{padding:15px}.section-heading.compact{margin-bottom:12px}.section-heading.compact h2{margin:0}.daily-chart{height:115px;display:flex;align-items:flex-end;gap:5px;padding-top:8px}.daily-bar{height:100%;flex:1;min-width:5px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px}.daily-bar span{width:100%;max-width:14px;min-height:2px;background:var(--accent);border-radius:3px 3px 1px 1px}.daily-bar small{font-size:8px;color:var(--muted)}
        .ranking-list{display:flex;flex-direction:column}.ranking-row{display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:9px;padding:9px 0;border-top:1px solid var(--border)}.ranking-row:first-child{border-top:0}.ranking-row strong,.ranking-row small{display:block}.ranking-row>strong{font-size:10px}.ranking-row div strong{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ranking-row small{font-size:9px;color:var(--muted);margin-top:3px}.rank{font-family:monospace;color:var(--muted);font-size:10px}.rep-avatar{width:25px;height:25px;display:grid;place-items:center;border-radius:6px;background:rgba(59,130,246,.12);color:var(--accent);font-size:10px;font-weight:800}
        @keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1200px){.metrics-grid{grid-template-columns:repeat(3,1fr)}.workspace-grid{grid-template-columns:1fr}.insights-column{display:grid;grid-template-columns:repeat(3,1fr)}}@media(max-width:780px){.secretary-content{padding:14px}.module-intro{align-items:flex-start;flex-direction:column}.instance-summary{width:100%}.filter-bar{align-items:stretch;flex-direction:column}.date-filter label{flex:1}.date-filter input{width:100%}.filter-bar select{width:100%}.metrics-grid{grid-template-columns:repeat(2,1fr)}.pipeline-grid{grid-template-columns:repeat(2,1fr)}.insights-column{grid-template-columns:1fr}.order-header{display:none}.order-row{grid-template-columns:1fr auto;padding:12px}.order-row>span:nth-child(3),.order-row>span:nth-child(4){display:none}.order-row>span:nth-child(5){grid-column:1}.order-details{grid-template-columns:1fr}.metric-card strong{font-size:18px}}
      `}</style>
    </div>
  );
}
