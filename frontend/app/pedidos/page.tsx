"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import { clicVendasApi } from "@/lib/api";
import type { Pedido, PedidoItem, SyncLog } from "@/lib/types";
import { RefreshCw, Activity, ShoppingCart, Users, ChevronLeft, ChevronRight, X, Package, Database } from "lucide-react";
import Link from "next/link";

function SitBadge({ sit }: { sit?: string }) {
  const s = (sit || "").toLowerCase();
  const color =
    s.includes("faturado") || s.includes("aprovado") || s.includes("fechado") || s.includes("integrado")
      ? "var(--success)"
      : s.includes("cancel")
        ? "var(--error)"
        : "var(--muted)";
  return (
    <span
      style={{
        padding: "2px 10px",
        borderRadius: 20,
        background: `${color}18`,
        color,
        border: `1px solid ${color}44`,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {sit || "-"}
    </span>
  );
}

function InfoChip({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <span style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5, display: "block" }}>
        {label}
      </span>
      <span style={{ fontSize: 13, fontWeight: highlight ? 700 : 500, color: highlight ? "var(--accent)" : "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}

function PedidoDrawer({ pedido, onClose }: { pedido: Pedido; onClose: () => void }) {
  const itens: PedidoItem[] = pedido.items_json || [];
  const totalCalculado = itens.reduce((sum, item) => sum + (item.vlrTotal || 0), 0);

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100, backdropFilter: "blur(2px)" }}
      />
      <div
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0,
          width: "min(620px, 92vw)",
          background: "var(--surface)", borderLeft: "1px solid var(--border)",
          zIndex: 101, display: "flex", flexDirection: "column",
          boxShadow: "-8px 0 32px rgba(0,0,0,0.3)",
        }}
      >
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <ShoppingCart size={16} color="var(--accent)" />
              <span style={{ fontSize: 18, fontWeight: 800, color: "var(--text)" }}>Pedido #{pedido.num_ped}</span>
              <SitBadge sit={pedido.sit_ped} />
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
              <InfoChip label="Cliente" value={pedido.customer_name || String(pedido.cod_cli || "-")} />
              <InfoChip label="CPF/CNPJ" value={String(pedido.cod_cli || "-")} />
              <InfoChip label="Data" value={pedido.dat_emi || "-"} />
              <InfoChip
                label="Total"
                value={pedido.order_total_value != null
                  ? `R$ ${pedido.order_total_value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                  : "-"}
                highlight
              />
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 8px", cursor: "pointer", color: "var(--muted)", display: "flex", alignItems: "center" }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "0 0 24px" }}>
          {itens.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted)", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <Package size={32} color="var(--border)" />
              <span>Nenhum item salvo para este pedido.</span>
            </div>
          ) : (
            <>
              <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  {itens.length} {itens.length === 1 ? "produto" : "produtos"}
                </span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Codigo", "Produto", "Qtd", "Unid", "Preco Unit.", "Total"].map((h) => (
                      <th key={h} style={{ padding: "9px 14px", textAlign: ["Qtd", "Preco Unit.", "Total"].includes(h) ? "right" : "left", fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5, whiteSpace: "nowrap" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {itens.map((item, idx) => (
                    <tr key={idx} style={{ borderTop: "1px solid var(--border)", background: idx % 2 === 0 ? "transparent" : "var(--surface2)44" }}>
                      <td style={{ padding: "10px 14px", fontSize: 12, color: "var(--accent)", fontWeight: 600, fontFamily: "monospace", whiteSpace: "nowrap" }}>{item.codPro || "-"}</td>
                      <td style={{ padding: "10px 14px", fontSize: 13, color: "var(--text)", maxWidth: 200 }}>{item.desPro || "-"}</td>
                      <td style={{ padding: "10px 14px", fontSize: 13, color: "var(--text)", textAlign: "right", fontWeight: 600, whiteSpace: "nowrap" }}>{item.qtdPed != null ? Number(item.qtdPed).toLocaleString("pt-BR") : "-"}</td>
                      <td style={{ padding: "10px 14px", fontSize: 11, color: "var(--muted)", textAlign: "right", whiteSpace: "nowrap" }}>{item.uniMed || "UN"}</td>
                      <td style={{ padding: "10px 14px", fontSize: 12, color: "var(--text)", textAlign: "right", whiteSpace: "nowrap" }}>
                        {item.preUni != null ? `R$ ${item.preUni.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "-"}
                      </td>
                      <td style={{ padding: "10px 14px", fontSize: 13, color: "var(--text)", fontWeight: 700, textAlign: "right", whiteSpace: "nowrap" }}>
                        {item.vlrTotal != null ? `R$ ${item.vlrTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>

        {itens.length > 0 && (
          <div style={{ padding: "16px 24px", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--surface2)" }}>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              {itens.length} {itens.length === 1 ? "item" : "itens"} · {itens.reduce((s, i) => s + (i.qtdPed || 0), 0).toLocaleString("pt-BR")} unidades
            </span>
            <div style={{ textAlign: "right" }}>
              <span style={{ fontSize: 11, color: "var(--muted)", display: "block", marginBottom: 2 }}>TOTAL DOS ITENS</span>
              <span style={{ fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
                R$ {totalCalculado.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default function PedidosPage() {
  const [loading, setLoading] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [lastLog, setLastLog] = useState<SyncLog | null>(null);
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [dias, setDias] = useState(0);
  const [loadingPedidos, setLoadingPedidos] = useState(false);
  const [selectedPedido, setSelectedPedido] = useState<Pedido | null>(null);

  const loadPedidos = useCallback(async (targetPage = 1) => {
    setLoadingPedidos(true);
    try {
      const result = await clicVendasApi.getPedidos({ dias, page: targetPage });
      setPedidos(result.pedidos);
      setTotal(result.total);
      setPages(result.pages);
      setPage(targetPage);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingPedidos(false);
    }
  }, [dias]);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    clicVendasApi.getSyncLogs(today).then((result) => {
      const last = result.logs.find((l) => l.status === "success" || l.status === "error");
      setLastLog(last || null);
    }).catch(() => null);
    loadPedidos(1);
  }, [loadPedidos]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setSelectedPedido(null); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleSync = async () => {
    setLoading(true);
    setSyncMsg(null);
    try {
      const syncWindow = dias > 0 ? dias : 30;
      const result = await clicVendasApi.sync(syncWindow);
      setSyncMsg(`${result.message}`);
      await loadPedidos(1);
      const today = new Date().toISOString().slice(0, 10);
      const logs = await clicVendasApi.getSyncLogs(today);
      setLastLog(logs.logs.find((l) => l.status === "success" || l.status === "error") || null);
    } catch (error) {
      setSyncMsg(`Erro: ${error instanceof Error ? error.message : "Falha ao sincronizar"}`);
    } finally {
      setLoading(false);
    }
  };

  const totalValue = pedidos.reduce((sum, p) => sum + (p.order_total_value || 0), 0);
  const uniqueClients = new Set(pedidos.map((p) => p.cod_cli)).size;
  const rangeLabel = dias === 0 ? "Toda a base local" : `Ultimos ${dias} dias`;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Pedidos" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
          <select
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            style={{ background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "7px 12px", fontSize: 13 }}
          >
            {[
              { value: 0, label: "Toda a base no banco" },
              { value: 7, label: "Ultimos 7 dias" },
              { value: 15, label: "Ultimos 15 dias" },
              { value: 30, label: "Ultimos 30 dias" },
              { value: 60, label: "Ultimos 60 dias" },
              { value: 90, label: "Ultimos 90 dias" },
            ].map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <button
            onClick={handleSync}
            disabled={loading}
            style={{ display: "flex", alignItems: "center", gap: 7, background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "8px 18px", fontWeight: 600, fontSize: 13, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1 }}
          >
            <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            {loading ? "Sincronizando..." : "Atualizar Base"}
          </button>

          <Link
            href="/pedidos/monitor"
            style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--muted)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 16px", fontSize: 13, textDecoration: "none", background: "transparent" }}
          >
            <Activity size={14} />
            Monitor de Syncs
          </Link>

          {syncMsg && (
            <span style={{ fontSize: 12, color: syncMsg.startsWith("Erro") ? "var(--error)" : "var(--success)" }}>
              {syncMsg}
            </span>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Pedidos na base", value: total, icon: ShoppingCart, color: "var(--accent)" },
            { label: "Clientes unicos", value: uniqueClients, icon: Users, color: "var(--success)" },
            { label: "Valor acumulado", value: `R$ ${totalValue.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`, icon: Database, color: "var(--warn)" },
            { label: "Ultima sync", value: lastLog ? new Date(lastLog.triggered_at).toLocaleTimeString("pt-BR") : "-", icon: RefreshCw, color: lastLog?.status === "success" ? "var(--success)" : "var(--muted)" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>{label}</span>
                <Icon size={16} color={color} />
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>{value}</div>
            </div>
          ))}
        </div>

        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontWeight: 700, fontSize: 13, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
              {rangeLabel}
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{total} registros</span>
          </div>

          {loadingPedidos ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : pedidos.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhum pedido encontrado.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Pedido", "Cliente", "Data", "Situacao", "Valor", "Itens"].map((h) => (
                      <th key={h} style={{ padding: "10px 16px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pedidos.map((pedido, index) => {
                    const isSelected = selectedPedido?.num_ped === pedido.num_ped;
                    return (
                      <tr
                        key={pedido.num_ped || index}
                        onClick={() => setSelectedPedido(pedido)}
                        style={{ borderTop: "1px solid var(--border)", cursor: "pointer", transition: "background 0.1s", background: isSelected ? "var(--accent)18" : "transparent" }}
                        onMouseEnter={(e) => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "var(--surface2)"; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = isSelected ? "var(--accent)18" : "transparent"; }}
                      >
                        <td style={{ padding: "10px 16px", fontSize: 13, color: "var(--accent)", fontWeight: 600 }}>#{pedido.num_ped}</td>
                        <td style={{ padding: "10px 16px", fontSize: 13, color: "var(--text)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {pedido.customer_name || String(pedido.cod_cli || "-")}
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 13, color: "var(--muted)", whiteSpace: "nowrap" }}>{pedido.dat_emi || "-"}</td>
                        <td style={{ padding: "10px 16px" }}><SitBadge sit={pedido.sit_ped} /></td>
                        <td style={{ padding: "10px 16px", fontSize: 13, color: "var(--text)", whiteSpace: "nowrap" }}>
                          {pedido.order_total_value != null
                            ? `R$ ${pedido.order_total_value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                            : "-"}
                        </td>
                        <td style={{ padding: "10px 16px" }}>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color: (pedido.items_json?.length || 0) > 0 ? "var(--text)" : "var(--muted)", background: (pedido.items_json?.length || 0) > 0 ? "var(--accent)18" : "transparent", padding: "2px 8px", borderRadius: 12, border: (pedido.items_json?.length || 0) > 0 ? "1px solid var(--accent)44" : "none" }}>
                            <Package size={11} />
                            {pedido.items_json?.length || 0} {(pedido.items_json?.length || 0) === 1 ? "item" : "itens"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {pages > 1 && (
            <div style={{ padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>Pagina {page} de {pages}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={() => loadPedidos(page - 1)} disabled={page <= 1} style={{ background: "var(--surface2)", border: "1px solid var(--border)", color: page <= 1 ? "var(--border)" : "var(--text)", borderRadius: 6, padding: "5px 10px", cursor: page <= 1 ? "not-allowed" : "pointer" }}>
                  <ChevronLeft size={14} />
                </button>
                <button onClick={() => loadPedidos(page + 1)} disabled={page >= pages} style={{ background: "var(--surface2)", border: "1px solid var(--border)", color: page >= pages ? "var(--border)" : "var(--text)", borderRadius: 6, padding: "5px 10px", cursor: page >= pages ? "not-allowed" : "pointer" }}>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedPedido && <PedidoDrawer pedido={selectedPedido} onClose={() => setSelectedPedido(null)} />}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
