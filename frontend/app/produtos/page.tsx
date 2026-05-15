"use client";

import { useCallback, useEffect, useState } from "react";
import { Package, RefreshCw, Search, X } from "lucide-react";
import Header from "@/components/layout/Header";
import { produtosApi } from "@/lib/api";
import type { Produto } from "@/lib/types";

const CATEGORIA_MAP: Record<string, string> = {
  SG: "Garrafa",
  SC: "Copo",
  CB: "Bolsa Conc.",
  SB: "Bolsa",
  GP: "Galão",
};

function categoria(cod: string): string {
  const prefix = cod.slice(0, 2).toUpperCase();
  return CATEGORIA_MAP[prefix] ?? cod.slice(0, 2);
}

function fmtPreco(v: number | null): string {
  if (v == null) return "-";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
        background: `${color}22`,
        color,
        border: `1px solid ${color}44`,
      }}
    >
      {label}
    </span>
  );
}

const CAT_COLORS: Record<string, string> = {
  Garrafa: "#3b82f6",
  Copo: "#8b5cf6",
  "Bolsa Conc.": "#f59e0b",
  Bolsa: "#10b981",
  Galão: "#ef4444",
};

export default function ProdutosPage() {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [loading, setLoading] = useState(false);
  const [busca, setBusca] = useState("");
  const [buscaInput, setBuscaInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (q?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await produtosApi.list({ busca: q || undefined });
      setProdutos(res.produtos);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setBusca(buscaInput);
    load(buscaInput);
  }

  function clearSearch() {
    setBuscaInput("");
    setBusca("");
    load();
  }

  const groups = produtos.reduce<Record<string, Produto[]>>((acc, p) => {
    const cat = categoria(p.cod_produto);
    (acc[cat] = acc[cat] || []).push(p);
    return acc;
  }, {});

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Produtos" subtitle={`${produtos.length} produto${produtos.length !== 1 ? "s" : ""} ativos`} />

      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        {/* Barra de busca */}
        <div style={{ display: "flex", gap: 12, marginBottom: 24, alignItems: "center" }}>
          <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, flex: 1, maxWidth: 420 }}>
            <div style={{ position: "relative", flex: 1 }}>
              <Search
                size={15}
                style={{
                  position: "absolute",
                  left: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--muted)",
                  pointerEvents: "none",
                }}
              />
              <input
                value={buscaInput}
                onChange={(e) => setBuscaInput(e.target.value)}
                placeholder="Buscar por nome ou código..."
                style={{
                  width: "100%",
                  padding: "8px 32px 8px 32px",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                  outline: "none",
                }}
              />
              {buscaInput && (
                <X
                  size={14}
                  onClick={clearSearch}
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    color: "var(--muted)",
                    cursor: "pointer",
                  }}
                />
              )}
            </div>
            <button
              type="submit"
              style={{
                padding: "8px 16px",
                background: "var(--accent)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Buscar
            </button>
          </form>

          <button
            onClick={() => load(busca)}
            disabled={loading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 14px",
              background: "transparent",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--muted)",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : "none" }} />
            Atualizar
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "#ef444420",
              border: "1px solid #ef444440",
              borderRadius: 8,
              color: "#ef4444",
              marginBottom: 20,
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {loading && produtos.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 14, textAlign: "center", marginTop: 60 }}>
            Carregando...
          </div>
        ) : produtos.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
              marginTop: 80,
              color: "var(--muted)",
            }}
          >
            <Package size={40} style={{ opacity: 0.3 }} />
            <span style={{ fontSize: 14 }}>Nenhum produto encontrado</span>
          </div>
        ) : (
          Object.entries(groups).map(([cat, items]) => (
            <div key={cat} style={{ marginBottom: 32 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Badge label={cat} color={CAT_COLORS[cat] ?? "var(--accent)"} />
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{items.length} produto{items.length !== 1 ? "s" : ""}</span>
              </div>

              <div
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  overflow: "hidden",
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Código", "Produto", "Deriv.", "Preço Base", "Preço Inst.299"].map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: "10px 16px",
                            textAlign: h.startsWith("Preço") ? "right" : "left",
                            color: "var(--muted)",
                            fontWeight: 500,
                            fontSize: 11,
                            textTransform: "uppercase",
                            letterSpacing: "0.05em",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((p, i) => (
                      <tr
                        key={p.id}
                        style={{
                          borderBottom: i < items.length - 1 ? "1px solid var(--border)" : "none",
                          transition: "background 0.1s",
                        }}
                        onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--border)")}
                        onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "transparent")}
                      >
                        <td style={{ padding: "10px 16px", color: "var(--muted)", fontFamily: "monospace", fontSize: 12 }}>
                          {p.cod_produto}
                        </td>
                        <td style={{ padding: "10px 16px", color: "var(--text)", fontWeight: 500 }}>
                          {p.nome}
                        </td>
                        <td style={{ padding: "10px 16px", color: "var(--muted)" }}>
                          {p.derivacao || "-"}
                        </td>
                        <td style={{ padding: "10px 16px", textAlign: "right", color: "var(--text)" }}>
                          {fmtPreco(p.preco_base)}
                        </td>
                        <td style={{ padding: "10px 16px", textAlign: "right", color: "var(--accent)", fontWeight: 600 }}>
                          {fmtPreco(p.preco_inst_299)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
