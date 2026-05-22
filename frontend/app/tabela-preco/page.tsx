"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, Download, Package, RefreshCw, Search, Tag, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { tabelaPrecoApi } from "@/lib/api";
import type { TabelaPreco, TabelaPrecoItem } from "@/lib/types";

export default function TabelaPrecoPage() {
  const [tabelas, setTabelas] = useState<TabelaPreco[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [tabelaSelecionada, setTabelaSelecionada] = useState<TabelaPreco | null>(null);
  const [itens, setItens] = useState<TabelaPrecoItem[]>([]);
  const [loadingItens, setLoadingItens] = useState(false);
  const [buscaItem, setBuscaItem] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await tabelaPrecoApi.list();
      setTabelas(data.tabelas);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar tabelas");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await tabelaPrecoApi.sync();
      setSyncMsg({
        type: "success",
        text: `Sincronizado: ${res.data.tabelas_upserted} tabelas, ${res.data.itens_upserted} produtos (${res.data.duration_ms}ms)`,
      });
      await load();
    } catch (e) {
      setSyncMsg({ type: "error", text: e instanceof Error ? e.message : "Erro ao sincronizar" });
    } finally {
      setSyncing(false);
    }
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  const abrirTabela = useCallback(async (tabela: TabelaPreco) => {
    setTabelaSelecionada(tabela);
    setItens([]);
    setBuscaItem("");
    setLoadingItens(true);
    try {
      const data = await tabelaPrecoApi.getItens(tabela.codigo_tabela);
      setItens(data.itens);
    } catch {
      setItens([]);
    } finally {
      setLoadingItens(false);
    }
  }, []);

  const fecharDrawer = () => {
    setTabelaSelecionada(null);
    setItens([]);
    setBuscaItem("");
  };

  const tabelasFiltradas = tabelas.filter((t) => {
    const q = busca.toLowerCase();
    return (
      t.codigo_tabela.toLowerCase().includes(q) ||
      (t.nome_tabela || "").toLowerCase().includes(q)
    );
  });

  const itensFiltrados = itens.filter((i) => {
    const q = buscaItem.toLowerCase();
    return (
      i.cod_produto.toLowerCase().includes(q) ||
      (i.nome_produto || "").toLowerCase().includes(q) ||
      (i.variacao || "").toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Tabela de Preço" />

      <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
        {/* Conteúdo principal */}
        <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
          {/* Barra de ações */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "8px 12px",
                flex: 1,
                maxWidth: 360,
              }}
            >
              <Search size={14} color="var(--muted)" />
              <input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar tabela..."
                style={{
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  color: "var(--text)",
                  fontSize: 13,
                  flex: 1,
                }}
              />
            </div>

            <button
              onClick={load}
              disabled={loading}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--muted)",
                fontSize: 13,
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              <RefreshCw size={14} style={{ opacity: loading ? 0.4 : 1 }} />
              Atualizar
            </button>

            <button
              onClick={handleSync}
              disabled={syncing}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 16px",
                borderRadius: 8,
                border: "none",
                background: syncing ? "var(--muted)" : "var(--accent)",
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: syncing ? "not-allowed" : "pointer",
              }}
            >
              <Download size={14} />
              {syncing ? "Sincronizando..." : "Sincronizar Tabela de Preço"}
            </button>
          </div>

          {/* Mensagem de feedback do sync */}
          {syncMsg && (
            <div
              style={{
                background: syncMsg.type === "success" ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                border: `1px solid ${syncMsg.type === "success" ? "var(--success, #22c55e)" : "var(--error)"}`,
                borderRadius: 8,
                padding: "10px 16px",
                marginBottom: 16,
                fontSize: 13,
                color: syncMsg.type === "success" ? "var(--success, #22c55e)" : "var(--error)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span>{syncMsg.text}</span>
              <button
                onClick={() => setSyncMsg(null)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: "0 4px" }}
              >
                <X size={14} />
              </button>
            </div>
          )}

          {/* Resumo */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 12,
              marginBottom: 20,
            }}
          >
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "16px 20px",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                TOTAL DE TABELAS
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text)" }}>{total}</div>
            </div>
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "16px 20px",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                TOTAL DE PRODUTOS (todas tabelas)
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text)" }}>
                {tabelas.reduce((acc, t) => acc + (t.total_itens || 0), 0)}
              </div>
            </div>
          </div>

          {/* Estado de loading / erro / vazio */}
          {loading && (
            <div style={{ textAlign: "center", padding: 48, color: "var(--muted)", fontSize: 14 }}>
              Carregando tabelas...
            </div>
          )}

          {!loading && error && (
            <div
              style={{
                background: "rgba(239,68,68,0.08)",
                border: "1px solid var(--error)",
                borderRadius: 8,
                padding: 16,
                color: "var(--error)",
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {!loading && !error && tabelasFiltradas.length === 0 && (
            <div
              style={{
                textAlign: "center",
                padding: 64,
                color: "var(--muted)",
                fontSize: 14,
              }}
            >
              <Tag size={32} style={{ marginBottom: 12, opacity: 0.4 }} />
              <div>Nenhuma tabela de preço encontrada.</div>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                Após configurar a integração com o Senior ERP, as tabelas aparecerão aqui.
              </div>
            </div>
          )}

          {/* Tabela de listagem */}
          {!loading && !error && tabelasFiltradas.length > 0 && (
            <div
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th
                      style={{
                        padding: "10px 16px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Código
                    </th>
                    <th
                      style={{
                        padding: "10px 16px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Nome
                    </th>
                    <th
                      style={{
                        padding: "10px 16px",
                        textAlign: "right",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Produtos
                    </th>
                    <th
                      style={{
                        padding: "10px 16px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Última sync
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {tabelasFiltradas.map((tabela) => (
                    <tr
                      key={tabela.codigo_tabela}
                      onClick={() => abrirTabela(tabela)}
                      style={{
                        borderBottom: "1px solid var(--border)",
                        cursor: "pointer",
                        transition: "background 0.1s",
                        background:
                          tabelaSelecionada?.codigo_tabela === tabela.codigo_tabela
                            ? "rgba(var(--accent-rgb, 99,102,241), 0.08)"
                            : "transparent",
                      }}
                      onMouseEnter={(e) => {
                        if (tabelaSelecionada?.codigo_tabela !== tabela.codigo_tabela) {
                          (e.currentTarget as HTMLTableRowElement).style.background =
                            "var(--surface-hover, rgba(255,255,255,0.04))";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (tabelaSelecionada?.codigo_tabela !== tabela.codigo_tabela) {
                          (e.currentTarget as HTMLTableRowElement).style.background = "transparent";
                        }
                      }}
                    >
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            fontFamily: "monospace",
                            fontSize: 13,
                            fontWeight: 600,
                            color: "var(--accent)",
                            background: "rgba(99,102,241,0.1)",
                            padding: "2px 8px",
                            borderRadius: 4,
                          }}
                        >
                          {tabela.codigo_tabela}
                        </span>
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          fontSize: 13,
                          color: "var(--text)",
                          fontWeight: 500,
                        }}
                      >
                        {tabela.nome_tabela || "—"}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          textAlign: "right",
                          fontSize: 13,
                          color: "var(--muted)",
                        }}
                      >
                        {tabela.total_itens ?? 0}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          fontSize: 12,
                          color: "var(--muted)",
                        }}
                      >
                        {tabela.synced_at
                          ? new Date(tabela.synced_at).toLocaleDateString("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Drawer lateral de itens */}
        {tabelaSelecionada && (
          <>
            <div
              onClick={fecharDrawer}
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.3)",
                zIndex: 40,
              }}
            />
            <div
              style={{
                position: "fixed",
                top: 0,
                right: 0,
                bottom: 0,
                width: 560,
                background: "var(--surface)",
                borderLeft: "1px solid var(--border)",
                zIndex: 50,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
              {/* Header do drawer */}
              <div
                style={{
                  padding: "20px 24px",
                  borderBottom: "1px solid var(--border)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 12,
                }}
              >
                <button
                  onClick={fecharDrawer}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--muted)",
                    padding: 4,
                    marginTop: 2,
                  }}
                >
                  <ChevronLeft size={18} />
                </button>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: 12,
                        fontWeight: 700,
                        color: "var(--accent)",
                        background: "rgba(99,102,241,0.12)",
                        padding: "2px 8px",
                        borderRadius: 4,
                      }}
                    >
                      {tabelaSelecionada.codigo_tabela}
                    </span>
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text)" }}>
                    {tabelaSelecionada.nome_tabela || "Sem nome"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    {loadingItens ? "Carregando..." : `${itensFiltrados.length} produto(s)`}
                  </div>
                </div>
                <button
                  onClick={fecharDrawer}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--muted)",
                    padding: 4,
                  }}
                >
                  <X size={16} />
                </button>
              </div>

              {/* Busca dentro da tabela */}
              <div style={{ padding: "12px 24px", borderBottom: "1px solid var(--border)" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    background: "var(--bg, #0f0f13)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "7px 12px",
                  }}
                >
                  <Search size={13} color="var(--muted)" />
                  <input
                    value={buscaItem}
                    onChange={(e) => setBuscaItem(e.target.value)}
                    placeholder="Buscar produto..."
                    style={{
                      border: "none",
                      outline: "none",
                      background: "transparent",
                      color: "var(--text)",
                      fontSize: 13,
                      flex: 1,
                    }}
                  />
                </div>
              </div>

              {/* Lista de itens */}
              <div style={{ flex: 1, overflowY: "auto" }}>
                {loadingItens && (
                  <div
                    style={{ textAlign: "center", padding: 40, color: "var(--muted)", fontSize: 13 }}
                  >
                    Carregando produtos...
                  </div>
                )}

                {!loadingItens && itensFiltrados.length === 0 && (
                  <div
                    style={{
                      textAlign: "center",
                      padding: 40,
                      color: "var(--muted)",
                      fontSize: 13,
                    }}
                  >
                    <Package size={28} style={{ marginBottom: 10, opacity: 0.4 }} />
                    <div>Nenhum produto nesta tabela.</div>
                  </div>
                )}

                {!loadingItens && itensFiltrados.length > 0 && (
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead
                      style={{
                        position: "sticky",
                        top: 0,
                        background: "var(--surface)",
                        zIndex: 1,
                      }}
                    >
                      <tr style={{ borderBottom: "1px solid var(--border)" }}>
                        <th
                          style={{
                            padding: "9px 24px",
                            textAlign: "left",
                            fontSize: 11,
                            fontWeight: 600,
                            color: "var(--muted)",
                            textTransform: "uppercase",
                          }}
                        >
                          Código
                        </th>
                        <th
                          style={{
                            padding: "9px 8px",
                            textAlign: "left",
                            fontSize: 11,
                            fontWeight: 600,
                            color: "var(--muted)",
                            textTransform: "uppercase",
                          }}
                        >
                          Produto
                        </th>
                        <th
                          style={{
                            padding: "9px 8px",
                            textAlign: "left",
                            fontSize: 11,
                            fontWeight: 600,
                            color: "var(--muted)",
                            textTransform: "uppercase",
                          }}
                        >
                          Var.
                        </th>
                        <th
                          style={{
                            padding: "9px 24px 9px 8px",
                            textAlign: "right",
                            fontSize: 11,
                            fontWeight: 600,
                            color: "var(--muted)",
                            textTransform: "uppercase",
                          }}
                        >
                          Preço
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {itensFiltrados.map((item) => (
                        <tr
                          key={`${item.cod_produto}-${item.variacao}-${item.quantidade_minima}`}
                          style={{ borderBottom: "1px solid var(--border)" }}
                        >
                          <td
                            style={{
                              padding: "10px 24px",
                              fontFamily: "monospace",
                              fontSize: 12,
                              color: "var(--muted)",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {item.cod_produto}
                          </td>
                          <td
                            style={{
                              padding: "10px 8px",
                              fontSize: 13,
                              color: "var(--text)",
                            }}
                          >
                            {item.nome_produto || "—"}
                          </td>
                          <td
                            style={{
                              padding: "10px 8px",
                              fontSize: 12,
                              color: "var(--muted)",
                            }}
                          >
                            {item.variacao || "—"}
                          </td>
                          <td
                            style={{
                              padding: "10px 24px 10px 8px",
                              textAlign: "right",
                              fontSize: 13,
                              fontWeight: 600,
                              color: "var(--success, #22c55e)",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {item.preco != null
                              ? `R$ ${Number(item.preco).toLocaleString("pt-BR", {
                                  minimumFractionDigits: 2,
                                  maximumFractionDigits: 2,
                                })}`
                              : "—"}
                            {item.desconto > 0 && (
                              <span
                                style={{
                                  marginLeft: 6,
                                  fontSize: 11,
                                  color: "var(--muted)",
                                  fontWeight: 400,
                                }}
                              >
                                -{item.desconto}%
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
