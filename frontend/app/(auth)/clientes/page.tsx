"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Mail, Phone, RefreshCw, Search, ShoppingCart, Users, Wallet, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { clientesApi } from "@/lib/api";
import type { Cliente, ClientesListResponse } from "@/lib/types";

function Drawer({ cliente, onClose }: { cliente: Cliente; onClose: () => void }) {
  const topProdutos = cliente.top_produtos_json || [];

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
          boxShadow: "-8px 0 32px rgba(0,0,0,0.3)",
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
            <div style={{ fontSize: 20, fontWeight: 800, color: "var(--text)", marginBottom: 6 }}>
              {cliente.nome || cliente.razao_social || cliente.documento || "Cliente"}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Chip label={`Cod. ${cliente.cod_cli ?? "—"}`} />
              <Chip label={cliente.ativo === false ? "Inativo" : "Ativo"} tone={cliente.ativo === false ? "error" : "success"} />
              {cliente.total_pedidos != null && <Chip label={`${cliente.total_pedidos} pedidos`} tone="accent" />}
            </div>
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

        <div style={{ padding: 24, display: "grid", gap: 16, overflow: "auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
            {[
              ["Razao social", cliente.razao_social || "—"],
              ["Fantasia", cliente.fantasia || "—"],
              ["Documento", cliente.documento || "—"],
              ["Email", cliente.email || "—"],
              ["Telefone", cliente.telefone || "—"],
              ["Cidade / UF", [cliente.cidade, cliente.uf].filter(Boolean).join(" / ") || "—"],
              ["Ultimo pedido", cliente.ultimo_pedido_numero ? `#${cliente.ultimo_pedido_numero}` : "—"],
              ["Valor do ultimo pedido", cliente.ultimo_pedido_valor != null ? `R$ ${cliente.ultimo_pedido_valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "—"],
              ["Ultima compra", cliente.ultimo_pedido_em ? new Date(cliente.ultimo_pedido_em).toLocaleString("pt-BR") : "—"],
              ["Proximo pedido estimado", cliente.proximo_pedido_estimado_em ? new Date(cliente.proximo_pedido_estimado_em).toLocaleDateString("pt-BR") : "—"],
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
                <div style={{ fontSize: 14, color: "var(--text)" }}>{value}</div>
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
                Top produtos
              </span>
            </div>
            {topProdutos.length === 0 ? (
              <div style={{ padding: 16, color: "var(--muted)", fontSize: 13 }}>Nenhum top produto consolidado.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {["Codigo", "Produto", "Qtd", "Valor"].map((header) => (
                      <th
                        key={header}
                        style={{
                          padding: "10px 14px",
                          textAlign: header === "Qtd" || header === "Valor" ? "right" : "left",
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
                  {topProdutos.slice(0, 8).map((produto, index) => (
                    <tr key={index} style={{ borderTop: "1px solid var(--border)" }}>
                      <td style={{ padding: "10px 14px", color: "var(--accent)", fontFamily: "monospace" }}>
                        {String(produto.codPro || "—")}
                      </td>
                      <td style={{ padding: "10px 14px", color: "var(--text)" }}>{String(produto.desPro || "—")}</td>
                      <td style={{ padding: "10px 14px", color: "var(--text)", textAlign: "right" }}>
                        {Number(produto.total_qtd || 0).toLocaleString("pt-BR")}
                      </td>
                      <td style={{ padding: "10px 14px", color: "var(--text)", textAlign: "right" }}>
                        R$ {Number(produto.total_valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function Chip({ label, tone = "accent" }: { label: string; tone?: "accent" | "success" | "error" }) {
  const colorMap = {
    accent: "var(--accent)",
    success: "var(--success)",
    error: "var(--error)",
  };
  const color = colorMap[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "4px 10px",
        borderRadius: 999,
        border: `1px solid ${color}55`,
        background: `${color}18`,
        color,
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {label}
    </span>
  );
}

export default function ClientesPage() {
  const [data, setData] = useState<ClientesListResponse | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);

  const load = useCallback(async (targetPage = 1, targetQuery = "") => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await clientesApi.list({ page: targetPage, query: targetQuery });
      setData(result);
      setPage(targetPage);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao carregar clientes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(1, "");
  }, [load]);

  const handleSync = async () => {
    setSyncing(true);
    setMessage(null);
    try {
      const result = await clientesApi.sync(query || undefined);
      setMessage(`${result.message} Dados do ultimo pedido recalculados a partir do banco local.`);
      await load(1, query);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao sincronizar clientes");
    } finally {
      setSyncing(false);
    }
  };

  const latestOrder = data?.clientes
    ?.map((row) => row.ultimo_pedido_em)
    .filter(Boolean)
    .sort()
    .at(-1);

  const totalValue = (data?.clientes || []).reduce((sum, cliente) => sum + Number(cliente.valor_total_acumulado || 0), 0);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Clientes - Base consolidada" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "0 12px",
            }}
          >
            <Search size={14} color="var(--muted)" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") load(1, query);
              }}
              placeholder="Buscar por codigo, nome, documento..."
              style={{
                width: 320,
                background: "transparent",
                border: "none",
                color: "var(--text)",
                outline: "none",
                padding: "9px 0",
                fontSize: 13,
              }}
            />
          </div>

          <button
            onClick={() => load(1, query)}
            style={{
              background: "transparent",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 14px",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Buscar
          </button>

          <button
            onClick={handleSync}
            disabled={syncing}
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
              cursor: syncing ? "not-allowed" : "pointer",
              opacity: syncing ? 0.7 : 1,
            }}
          >
            <RefreshCw size={14} style={{ animation: syncing ? "spin 1s linear infinite" : undefined }} />
            {syncing ? "Atualizando..." : "Atualizar Cadastro"}
          </button>

          {message && (
            <span style={{ fontSize: 12, color: message.toLowerCase().includes("falha") ? "var(--error)" : "var(--success)" }}>
              {message}
            </span>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Total clientes", value: data?.total ?? 0, icon: Users, color: "var(--accent)" },
            { label: "Clientes ativos", value: data?.active ?? 0, icon: ShoppingCart, color: "var(--success)" },
            { label: "Valor acumulado", value: `R$ ${totalValue.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`, icon: Wallet, color: "var(--warn)" },
            { label: "Ultimo pedido na base", value: latestOrder ? new Date(latestOrder).toLocaleDateString("pt-BR") : "—", icon: RefreshCw, color: "var(--accent)" },
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
              Clientes com ultimo pedido consolidado
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              clique na linha para abrir detalhes
            </span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : !data || data.clientes.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhum cliente consolidado. Atualize o cadastro para popular os dados locais.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Codigo", "Cliente", "Documento", "Contato", "Ultimo pedido", "Valor ultimo pedido"].map((header) => (
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
                  {data.clientes.map((cliente, index) => (
                    <tr
                      key={cliente.external_id || index}
                      onClick={() => cliente.cod_cli && setSelectedCliente(cliente)}
                      style={{
                        borderTop: "1px solid var(--border)",
                        cursor: cliente.cod_cli ? "pointer" : "default",
                      }}
                      onMouseEnter={(e) => {
                        if (cliente.cod_cli) {
                          (e.currentTarget as HTMLElement).style.background = "var(--surface2)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "transparent";
                      }}
                    >
                      <td style={{ padding: "10px 16px", color: "var(--accent)", fontWeight: 700 }}>
                        {cliente.cod_cli ?? "—"}
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        <div style={{ display: "grid", gap: 4 }}>
                          <span>{cliente.nome || cliente.razao_social || cliente.documento || "—"}</span>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>
                            {cliente.total_pedidos ?? 0} pedidos • R$ {Number(cliente.valor_total_acumulado || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--muted)", fontFamily: "monospace" }}>
                        {cliente.documento || "—"}
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        <div style={{ display: "grid", gap: 6 }}>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                            <Mail size={12} color="var(--muted)" />
                            {cliente.email || "—"}
                          </span>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                            <Phone size={12} color="var(--muted)" />
                            {cliente.telefone || "—"}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        <div style={{ display: "grid", gap: 4 }}>
                          <span>{cliente.ultimo_pedido_numero ? `#${cliente.ultimo_pedido_numero}` : "—"}</span>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>
                            {cliente.ultimo_pedido_em ? new Date(cliente.ultimo_pedido_em).toLocaleDateString("pt-BR") : "Sem historico"}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)", fontWeight: 700 }}>
                        {cliente.ultimo_pedido_valor != null
                          ? `R$ ${cliente.ultimo_pedido_valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                          : "—"}
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
                  onClick={() => load(page - 1, query)}
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
                  onClick={() => load(page + 1, query)}
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

      {selectedCliente && <Drawer cliente={selectedCliente} onClose={() => setSelectedCliente(null)} />}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
