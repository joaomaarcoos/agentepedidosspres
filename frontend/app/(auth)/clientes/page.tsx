"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Mail, Phone, RefreshCw, Search, ShoppingCart, Users, Wallet, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { clientesApi, representantesApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { Cliente, ClientesListResponse, RepresentanteOption } from "@/lib/types";

function Drawer({ cliente, onClose }: { cliente: Cliente; onClose: () => void }) {
  const topProdutos = cliente.top_produtos_json || [];
  const initials = (cliente.nome || cliente.razao_social || "C")
    .split(" ")
    .slice(0, 2)
    .map((w: string) => w[0])
    .join("")
    .toUpperCase();

  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 100, backdropFilter: "blur(2px)" }} />
      <div style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: "min(660px, 94vw)", background: "var(--surface)", borderLeft: "1px solid var(--border)", zIndex: 101, display: "flex", flexDirection: "column", boxShadow: "-8px 0 40px rgba(0,0,0,0.35)" }}>

        <div style={{ background: "linear-gradient(135deg, #0a2e1a 0%, #0d1f0d 100%)", padding: "24px 24px 20px", position: "relative", flexShrink: 0 }}>
          <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, padding: "6px 8px", cursor: "pointer", color: "rgba(255,255,255,0.7)", display: "flex", alignItems: "center" }}>
            <X size={16} />
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: "rgba(34,197,94,0.2)", border: "2px solid rgba(34,197,94,0.4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 800, color: "#4ade80", flexShrink: 0 }}>
              {initials}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 3 }}>
                {cliente.nome || cliente.razao_social || cliente.documento || "Cliente"}
              </div>
              {cliente.razao_social && cliente.nome !== cliente.razao_social && (
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {cliente.razao_social}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Chip label={`Cod. ${cliente.cod_cli ?? "—"}`} />
            <Chip label={cliente.ativo === false ? "Inativo" : "Ativo"} tone={cliente.ativo === false ? "error" : "success"} />
            {cliente.total_pedidos != null && <Chip label={`${cliente.total_pedidos} pedidos`} tone="accent" />}
            {cliente.valor_total_acumulado != null && (
              <Chip label={`R$ ${Number(cliente.valor_total_acumulado).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`} tone="accent" />
            )}
          </div>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 20 }}>

          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
              Identificação e contato
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
              {([
                ["Razão social", cliente.razao_social || "—"],
                ["Fantasia", cliente.fantasia || "—"],
                ["Documento", cliente.documento || "—"],
                ["Cidade / UF", [cliente.cidade, cliente.uf].filter(Boolean).join(" / ") || "—"],
                ["Email", cliente.email || "—"],
                ["Telefone", cliente.telefone || "—"],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
                  <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500, wordBreak: "break-word" }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
              Histórico de compras
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
              {([
                ["Último pedido", cliente.ultimo_pedido_numero ? `#${cliente.ultimo_pedido_numero}` : "—"],
                ["Data da última compra", cliente.ultimo_pedido_em ? new Date(cliente.ultimo_pedido_em).toLocaleDateString("pt-BR") : "—"],
                ["Valor do último pedido", cliente.ultimo_pedido_valor != null ? `R$ ${cliente.ultimo_pedido_valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "—"],
                ["Próximo pedido estimado", cliente.proximo_pedido_estimado_em ? new Date(cliente.proximo_pedido_estimado_em).toLocaleDateString("pt-BR") : "—"],
              ] as [string, string][]).map(([label, value]) => (
                <div key={label} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
                  <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          {topProdutos.length > 0 && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
                Top produtos{topProdutos.length > 8 ? ` — top 8 de ${topProdutos.length}` : ` — ${topProdutos.length} produtos`}
              </div>
              <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
                {topProdutos.slice(0, 8).map((produto, index) => (
                  <div key={index} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderBottom: index < Math.min(topProdutos.length, 8) - 1 ? "1px solid var(--border)" : "none" }}>
                    <div style={{ width: 30, height: 30, borderRadius: 8, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#818cf8", flexShrink: 0 }}>
                      {index + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500, marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {String(produto.desPro || "—")}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "monospace" }}>
                        {String(produto.codPro || "—")}
                      </div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                        {Number(produto.total_qtd || 0).toLocaleString("pt-BR")} un
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>
                        R$ {Number(produto.total_valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {topProdutos.length === 0 && (
            <div style={{ padding: "20px 16px", textAlign: "center", color: "var(--muted)", fontSize: 13, background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 12 }}>
              Nenhum top produto consolidado.
            </div>
          )}
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
  const { profile } = useAuth();
  const canFilterRep = profile?.role !== "representante";
  const [data, setData] = useState<ClientesListResponse | null>(null);
  const [query, setQuery] = useState("");
  const [codRep, setCodRep] = useState("");
  const [representantes, setRepresentantes] = useState<RepresentanteOption[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedCliente, setSelectedCliente] = useState<Cliente | null>(null);

  const load = useCallback(async (targetPage = 1, targetQuery = "") => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await clientesApi.list({
        page: targetPage,
        query: targetQuery,
        cod_rep: canFilterRep && codRep ? Number(codRep) : undefined,
      });
      setData(result);
      setPage(targetPage);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Falha ao carregar clientes");
    } finally {
      setLoading(false);
    }
  }, [canFilterRep, codRep]);

  useEffect(() => {
    load(1, "");
  }, [load]);

  useEffect(() => {
    if (!canFilterRep) return;
    representantesApi.list()
      .then((result) => setRepresentantes(result.representantes))
      .catch(() => setRepresentantes([]));
  }, [canFilterRep]);

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
  const quickReps = representantes.filter((rep) =>
    ["ELIEZER", "ALEXANDRE"].some((name) => rep.name.toUpperCase().includes(name))
  );

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

          {canFilterRep && (
            <select
              value={codRep}
              onChange={(e) => setCodRep(e.target.value)}
              style={{
                width: 360,
                background: "var(--surface2)",
                color: "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "8px 12px",
                fontSize: 13,
                outline: "none",
              }}
            >
              <option value="">Todos os representantes</option>
              {representantes
                .filter((rep) => rep.active || rep.orders_count > 0)
                .map((rep) => (
                  <option key={rep.cod_rep} value={rep.cod_rep}>
                    {rep.name} - Doc. {rep.document || "nao informado"} - Cod. {rep.cod_rep}
                  </option>
                ))}
            </select>
          )}
          {canFilterRep && (
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
          )}

          {message && (
            <span style={{ fontSize: 12, color: message.toLowerCase().includes("falha") ? "var(--error)" : "var(--success)" }}>
              {message}
            </span>
          )}
        </div>

        {canFilterRep && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: -12, marginBottom: 20 }}>
            <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.8 }}>
              Filtros rapidos
            </span>
            <button
              onClick={() => {
                setCodRep("");
                setQuery("");
                load(1, "");
              }}
              style={{ background: "var(--surface2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: 12, cursor: "pointer" }}
            >
              Todos
            </button>
            {quickReps.map((rep) => (
              <button
                key={rep.cod_rep}
                onClick={() => {
                  setCodRep(String(rep.cod_rep));
                  setQuery("");
                }}
                style={{ background: String(rep.cod_rep) === codRep ? "var(--accent)" : "var(--surface2)", color: String(rep.cod_rep) === codRep ? "#fff" : "var(--text)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: 12, cursor: "pointer" }}
              >
                {rep.name.split(" ")[0]} - {rep.document || `Cod. ${rep.cod_rep}`}
              </button>
            ))}
            <button
              onClick={() => {
                setQuery("");
                load(1, "");
              }}
              style={{ background: "transparent", color: "var(--muted)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: 12, cursor: "pointer" }}
            >
              Limpar busca
            </button>
          </div>
        )}

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
