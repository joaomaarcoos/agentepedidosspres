"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, ChevronLeft, ChevronRight, RefreshCw, Repeat2, Timer, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { recorrenciaApi } from "@/lib/api";
import type { Pedido, RecorrenciaCliente, RecorrenciaOverview } from "@/lib/types";

function StatusBadge({ status }: { status: RecorrenciaCliente["status"] }) {
  const colorMap: Record<RecorrenciaCliente["status"], string> = {
    critico: "var(--error)",
    atrasado: "var(--warn)",
    em_janela: "var(--success)",
    cedo: "var(--accent)",
    novo: "var(--muted)",
  };
  const color = colorMap[status];

  return (
    <span
      style={{
        padding: "4px 10px",
        borderRadius: 999,
        background: `${color}18`,
        color,
        border: `1px solid ${color}44`,
        fontSize: 11,
        fontWeight: 700,
        textTransform: "uppercase",
      }}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function DetailDrawer({ data, onClose }: { data: RecorrenciaCliente; onClose: () => void }) {
  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.45)",
          zIndex: 100,
          backdropFilter: "blur(2px)",
        }}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(620px, 92vw)",
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 20, fontWeight: 800, color: "var(--text)" }}>{data.cliente_nome}</span>
              <StatusBadge status={data.status} />
            </div>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>Cliente #{data.cod_cli}</div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "6px 8px",
              cursor: "pointer",
              color: "var(--muted)",
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: 24, overflow: "auto", display: "grid", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
            {[
              ["Pedidos", String(data.pedido_count)],
              ["Intervalo medio", data.avg_interval_days != null ? `${data.avg_interval_days} dias` : "—"],
              ["Ultima compra", data.last_order_at || "—"],
              ["Proxima prevista", data.expected_next_order_at || "—"],
              ["Dias sem comprar", data.days_since_last != null ? `${data.days_since_last}` : "—"],
              ["Atraso", `${data.overdue_days} dias`],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: "14px 16px",
                }}
              >
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
                  {label}
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text)" }}>{value}</div>
              </div>
            ))}
          </div>

          <div
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
              <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>
                Ultimos pedidos
              </span>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Pedido", "Data", "Valor", "Status"].map((header) => (
                    <th
                      key={header}
                      style={{
                        padding: "10px 14px",
                        textAlign: "left",
                        fontSize: 10,
                        fontWeight: 700,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                      }}
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.recent_orders.map((order: Pedido, index) => (
                  <tr key={order.num_ped || index} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px 14px", color: "var(--accent)", fontWeight: 700 }}>#{order.num_ped}</td>
                    <td style={{ padding: "10px 14px", color: "var(--text)" }}>{order.dat_emi || "—"}</td>
                    <td style={{ padding: "10px 14px", color: "var(--text)" }}>
                      {order.order_total_value != null
                        ? `R$ ${order.order_total_value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                        : "—"}
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--muted)" }}>{order.sit_ped || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

export default function RecorrenciaPage() {
  const [dias, setDias] = useState(180);
  const [minPedidos, setMinPedidos] = useState(2);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<RecorrenciaOverview | null>(null);
  const [selected, setSelected] = useState<RecorrenciaCliente | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async (targetPage = 1, targetDias = dias, targetMinPedidos = minPedidos) => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.list({
        dias: targetDias,
        minPedidos: targetMinPedidos,
        page: targetPage,
      });
      setData(result);
      setPage(targetPage);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao calcular recorrencia");
    } finally {
      setLoading(false);
    }
  }, [dias, minPedidos]);

  useEffect(() => {
    load(1, dias, minPedidos);
  }, [load, dias, minPedidos]);

  const openDetail = async (codCli: number) => {
    try {
      const detail = await recorrenciaApi.detail(codCli, dias);
      setSelected(detail);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao abrir detalhe");
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Recorrencia - ClicVendas" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <select
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            style={{
              background: "var(--surface2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "7px 12px",
              fontSize: 13,
            }}
          >
            {[60, 90, 180, 365].map((value) => (
              <option key={value} value={value}>
                Janela de {value} dias
              </option>
            ))}
          </select>

          <select
            value={minPedidos}
            onChange={(e) => setMinPedidos(Number(e.target.value))}
            style={{
              background: "var(--surface2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "7px 12px",
              fontSize: 13,
            }}
          >
            {[2, 3, 4, 5].map((value) => (
              <option key={value} value={value}>
                Minimo {value} pedidos
              </option>
            ))}
          </select>

          <button
            onClick={() => load(1, dias, minPedidos)}
            disabled={loading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              background: "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "8px 18px",
              fontWeight: 600,
              fontSize: 13,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            {loading ? "Calculando..." : "Recalcular"}
          </button>

          {message && <span style={{ fontSize: 12, color: "var(--error)" }}>{message}</span>}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Clientes mapeados", value: data?.total ?? 0, icon: Repeat2, color: "var(--accent)" },
            { label: "Criticos", value: data?.stats.criticos ?? 0, icon: AlertTriangle, color: "var(--error)" },
            { label: "Atrasados", value: data?.stats.atrasados ?? 0, icon: Timer, color: "var(--warn)" },
            { label: "Em janela", value: data?.stats.em_janela ?? 0, icon: CalendarClock, color: "var(--success)" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: "16px 20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  {label}
                </span>
                <Icon size={16} color={color} />
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>{value}</div>
            </div>
          ))}
        </div>

        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 16,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "16px 20px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontWeight: 700, fontSize: 13, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
              Mapa de recorrencia
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              baseado nos pedidos sincronizados de ClicVendas
            </span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : !data || data.clientes.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhuma recorrencia encontrada. Sincronize pedidos e aumente a janela de analise.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Cliente", "Status", "Pedidos", "Ultima compra", "Intervalo medio", "Atraso", "Ticket medio"].map((header) => (
                      <th
                        key={header}
                        style={{
                          padding: "10px 16px",
                          textAlign: "left",
                          fontSize: 11,
                          fontWeight: 700,
                          color: "var(--muted)",
                          textTransform: "uppercase",
                          letterSpacing: 0.5,
                        }}
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.clientes.map((cliente) => (
                    <tr
                      key={cliente.cod_cli}
                      onClick={() => openDetail(cliente.cod_cli)}
                      style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "var(--surface2)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "transparent";
                      }}
                    >
                      <td style={{ padding: "10px 16px" }}>
                        <div style={{ color: "var(--text)", fontWeight: 700 }}>{cliente.cliente_nome}</div>
                        <div style={{ color: "var(--muted)", fontSize: 12 }}>#{cliente.cod_cli}</div>
                      </td>
                      <td style={{ padding: "10px 16px" }}>
                        <StatusBadge status={cliente.status} />
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>{cliente.pedido_count}</td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>{cliente.last_order_at || "—"}</td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        {cliente.avg_interval_days != null ? `${cliente.avg_interval_days} dias` : "—"}
                      </td>
                      <td style={{ padding: "10px 16px", color: cliente.overdue_days > 0 ? "var(--warn)" : "var(--muted)", fontWeight: 700 }}>
                        {cliente.overdue_days} dias
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        R$ {cliente.avg_order_value.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(data?.pages || 1) > 1 && (
            <div
              style={{
                padding: "12px 20px",
                borderTop: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Pagina {page} de {data?.pages}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => load(page - 1, dias, minPedidos)}
                  disabled={page <= 1}
                  style={{
                    background: "var(--surface2)",
                    border: "1px solid var(--border)",
                    color: page <= 1 ? "var(--border)" : "var(--text)",
                    borderRadius: 6,
                    padding: "5px 10px",
                    cursor: page <= 1 ? "not-allowed" : "pointer",
                  }}
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  onClick={() => load(page + 1, dias, minPedidos)}
                  disabled={page >= (data?.pages || 1)}
                  style={{
                    background: "var(--surface2)",
                    border: "1px solid var(--border)",
                    color: page >= (data?.pages || 1) ? "var(--border)" : "var(--text)",
                    borderRadius: 6,
                    padding: "5px 10px",
                    cursor: page >= (data?.pages || 1) ? "not-allowed" : "pointer",
                  }}
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selected && <DetailDrawer data={selected} onClose={() => setSelected(null)} />}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
