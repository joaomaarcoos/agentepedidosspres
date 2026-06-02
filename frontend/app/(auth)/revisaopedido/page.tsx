"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Loader2,
  Package,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  User,
  X,
  XCircle,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { produtosApi, revisaoPedidoApi } from "@/lib/api";
import type { PedidoRevisao, PedidoRevisaoItem, PedidoRevisaoListResponse, PedidoRevisaoStatus, Produto } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_LABEL: Record<PedidoRevisaoStatus, string> = {
  pendente: "Pendente",
  em_revisao: "Em Revisão",
  pedido_feito: "Pedido Feito",
  cancelado: "Cancelado",
};

const STATUS_COLOR: Record<PedidoRevisaoStatus, string> = {
  pendente: "var(--warn)",
  em_revisao: "var(--accent)",
  pedido_feito: "var(--success)",
  cancelado: "var(--error)",
};

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function fmtPhone(phone: string) {
  const d = phone.replace(/\D/g, "");
  if (d.length === 13) return `+${d.slice(0, 2)} (${d.slice(2, 4)}) ${d.slice(4, 9)}-${d.slice(9)}`;
  if (d.length === 12) return `+${d.slice(0, 2)} (${d.slice(2, 4)}) ${d.slice(4, 8)}-${d.slice(8)}`;
  return phone;
}

function itemNome(item: PedidoRevisao["itens_json"][number]) {
  const nome = item.nome?.trim();
  if (nome) return nome;
  const tipo = item.tipo || item.formato;
  const produto = item.produto;
  const tamanho = item.tamanho || item.derivacao || item.variacao || item.volume;
  return [tipo, produto, tamanho].filter(Boolean).join(" ").toUpperCase() || "Item";
}

function itemQuantidade(item: PedidoRevisao["itens_json"][number]) {
  return [item.quantidade, item.unidade].filter(Boolean).join(" ") || "-";
}

function pedidoProtocolo(pedido: PedidoRevisao) {
  return pedido.protocolo || `SP-${pedido.id.slice(0, 8).toUpperCase()}`;
}

function normalizeKey(value?: string | null) {
  return String(value || "").trim().toUpperCase();
}

function productOptionValue(produto: Produto) {
  return `${normalizeKey(produto.cod_produto)}::${normalizeKey(produto.derivacao)}`;
}

function selectedProductValue(item: PedidoRevisaoItem) {
  const code = normalizeKey(item.cod_produto);
  if (!code) return "";
  const variation = normalizeKey(item.derivacao || item.tamanho || item.variacao || item.volume);
  return `${code}::${variation}`;
}

function inferTipoFromName(nome: string) {
  const value = normalizeKey(nome);
  if (value.includes("BOLSA") && value.includes("CONC")) return "bolsa concentrada";
  if (value.includes("BOLSA")) return "bolsa";
  if (value.includes("COPO")) return "copo";
  if (value.includes("GARRAFA")) return "garrafa";
  if (value.includes("GALAO") || value.includes("GALÃO")) return "galão";
  return "";
}

function defaultUnitForType(tipo: string) {
  const value = normalizeKey(tipo);
  if (value.includes("COPO")) return "copos";
  if (value.includes("GARRAFA")) return "garrafas";
  if (value.includes("BOLSA")) return "bolsas";
  if (value.includes("GALAO") || value.includes("GALÃO")) return "galões";
  return "unidades";
}

function productLabel(produto: Produto) {
  const derivacao = produto.derivacao ? ` - ${produto.derivacao}` : "";
  return `${produto.cod_produto} | ${produto.nome}${derivacao}`;
}

function itemFromProduct(produto: Produto): Partial<PedidoRevisaoItem> {
  const tipo = inferTipoFromName(produto.nome);
  return {
    cod_produto: produto.cod_produto,
    nome: produto.nome,
    produto: produto.nome,
    tipo,
    tamanho: produto.derivacao,
    derivacao: produto.derivacao,
    variacao: produto.derivacao,
    unidade: defaultUnitForType(tipo),
    preco_unitario: produto.preco_tabela_201 ?? produto.preco_tabela_202 ?? produto.preco_base ?? undefined,
  };
}

// ---------------------------------------------------------------------------
// Detail Modal
// ---------------------------------------------------------------------------

function DetailModal({
  pedido,
  produtos,
  onClose,
  onSetStatus,
  onUpdate,
  loading,
}: {
  pedido: PedidoRevisao;
  produtos: Produto[];
  onClose: () => void;
  onSetStatus: (status: PedidoRevisaoStatus) => void;
  onUpdate: (payload: { itens_json: PedidoRevisaoItem[]; observacoes: string }) => void;
  loading: boolean;
}) {
  const color = STATUS_COLOR[pedido.status];
  const productOptions = useMemo(
    () => {
      const unique = new Map<string, Produto>();
      produtos
        .filter((produto) => produto.ativo !== false)
        .forEach((produto) => {
          const key = productOptionValue(produto);
          if (!unique.has(key)) unique.set(key, produto);
        });
      return Array.from(unique.values()).sort((a, b) => productLabel(a).localeCompare(productLabel(b), "pt-BR"));
    },
    [produtos]
  );
  const productsByValue = useMemo(
    () => new Map(productOptions.map((produto) => [productOptionValue(produto), produto])),
    [productOptions]
  );
  const [editing, setEditing] = useState(false);
  const [editItems, setEditItems] = useState<PedidoRevisaoItem[]>(pedido.itens_json.map((item) => ({ ...item })));
  const [editObservacoes, setEditObservacoes] = useState(pedido.observacoes || "");

  function updateEditItem(index: number, patch: Partial<PedidoRevisaoItem>) {
    setEditItems((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function addEditItem() {
    setEditItems((items) => [...items, { nome: "", quantidade: "", unidade: "unidades" }]);
  }

  function removeEditItem(index: number) {
    setEditItems((items) => items.filter((_, i) => i !== index));
  }

  function saveEdit() {
    const itens_json = editItems
      .map((item) => ({
        ...item,
        nome: String(item.nome || item.produto || "").trim(),
        produto: String(item.produto || item.nome || "").trim(),
        unidade: String(item.unidade || "").trim(),
        quantidade: typeof item.quantidade === "string" ? item.quantidade.trim() : item.quantidade,
      }))
      .filter((item) => item.cod_produto || item.nome || item.produto || item.quantidade);
    onUpdate({ itens_json, observacoes: editObservacoes });
    setEditing(false);
  }

  useEffect(() => {
    setEditItems(pedido.itens_json.map((item) => ({ ...item })));
    setEditObservacoes(pedido.observacoes || "");
    setEditing(false);
  }, [pedido.id, pedido.itens_json, pedido.observacoes]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: 20,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 16, width: "100%", maxWidth: 680,
          maxHeight: "90vh", display: "flex", flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px", borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", gap: 12,
          }}
        >
          <Package size={18} color="var(--accent)" />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: "var(--text)" }}>
              {pedido.cliente_nome || "Cliente"}
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>
              {fmtPhone(pedido.cliente_telefone)} · {fmtDate(pedido.created_at)}
            </div>
            <div style={{ fontSize: 11, color: "var(--accent)", marginTop: 4, fontWeight: 700 }}>
              Protocolo {pedidoProtocolo(pedido)}
            </div>
          </div>
          <span
            style={{
              fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 6,
              color, background: `${color}18`, border: `1px solid ${color}40`,
            }}
          >
            {STATUS_LABEL[pedido.status]}
          </span>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 4 }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 18 }}>

          {/* Itens do pedido */}
          <section>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
              Itens do Pedido
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {editing ? (
                <>
                  {editItems.map((item, i) => (
                    <div
                      key={i}
                      style={{
                        display: "grid", gridTemplateColumns: "minmax(240px, 1fr) 96px 116px 34px", gap: 8, alignItems: "center",
                        background: "var(--surface2)", borderRadius: 8, padding: 8,
                        border: "1px solid var(--border)",
                      }}
                    >
                      <select
                        value={productsByValue.has(selectedProductValue(item)) ? selectedProductValue(item) : `manual:${i}`}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (!value || value.startsWith("manual:")) return;
                          const produto = productsByValue.get(value);
                          if (produto) updateEditItem(i, itemFromProduct(produto));
                        }}
                        style={{
                          background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6,
                          padding: "8px 10px", color: "var(--text)", fontSize: 13, outline: "none",
                        }}
                      >
                        {!productsByValue.has(selectedProductValue(item)) && (
                          <option value={`manual:${i}`}>{itemNome(item) || "Selecione o produto"}</option>
                        )}
                        <option value="">Selecione o produto</option>
                        {productOptions.map((produto) => (
                          <option key={productOptionValue(produto)} value={productOptionValue(produto)}>
                            {productLabel(produto)}
                          </option>
                        ))}
                      </select>
                      <input
                        value={String(item.quantidade ?? "")}
                        onChange={(e) => updateEditItem(i, { quantidade: e.target.value })}
                        placeholder="Qtd."
                        style={{
                          background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6,
                          padding: "8px 10px", color: "var(--text)", fontSize: 13, outline: "none",
                        }}
                      />
                      <select
                        value={String(item.unidade || "unidades")}
                        onChange={(e) => updateEditItem(i, { unidade: e.target.value })}
                        style={{
                          background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6,
                          padding: "8px 10px", color: "var(--text)", fontSize: 13, outline: "none",
                        }}
                      >
                        {["unidades", "copos", "garrafas", "bolsas", "galões"].map((unit) => (
                          <option key={unit} value={unit}>{unit}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => removeEditItem(i)}
                        disabled={loading}
                        title="Remover item"
                        style={{
                          height: 34, borderRadius: 7, border: "1px solid rgba(239,68,68,0.25)",
                          background: "rgba(239,68,68,0.08)", color: "var(--error)", cursor: loading ? "not-allowed" : "pointer",
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  <button
                    onClick={addEditItem}
                    disabled={loading}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                      background: "rgba(99,102,241,0.1)", color: "var(--accent)",
                      border: "1px dashed rgba(99,102,241,0.35)", borderRadius: 8,
                      padding: "8px 12px", fontSize: 13, fontWeight: 600,
                      cursor: loading ? "not-allowed" : "pointer",
                    }}
                  >
                    <Plus size={14} />
                    Adicionar item
                  </button>
                </>
              ) : (
                pedido.itens_json.map((item, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      background: "var(--surface2)", borderRadius: 8, padding: "8px 12px",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>{itemNome(item)}</span>
                    <span
                      style={{
                        fontSize: 12, fontWeight: 700, color: "var(--accent)",
                        background: "rgba(99,102,241,0.1)", borderRadius: 5, padding: "2px 8px",
                      }}
                    >
                      {itemQuantidade(item)}
                    </span>
                  </div>
                ))
              )}
              {!editing && pedido.itens_json.length === 0 && (
                <span style={{ fontSize: 12, color: "var(--muted)" }}>Nenhum item registrado</span>
              )}
            </div>
          </section>

          {/* Observações */}
          {(pedido.observacoes || editing) && (
            <section>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
                Observações
              </div>
              {editing ? (
                <textarea
                  value={editObservacoes}
                  onChange={(e) => setEditObservacoes(e.target.value)}
                  placeholder="Observações do pedido"
                  rows={3}
                  style={{
                    width: "100%", resize: "vertical", background: "var(--surface2)", borderRadius: 8,
                    padding: "10px 12px", fontSize: 13, color: "var(--text)", border: "1px solid var(--border)",
                    outline: "none",
                  }}
                />
              ) : (
                <div
                  style={{
                    background: "var(--surface2)", borderRadius: 8, padding: "10px 12px",
                    fontSize: 13, color: "var(--text)", border: "1px solid var(--border)",
                  }}
                >
                  {pedido.observacoes}
                </div>
              )}
            </section>
          )}

          {/* Mensagem original */}
          {pedido.mensagem_cliente && (
            <section>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
                Mensagem Original
              </div>
              <div
                style={{
                  background: "rgba(34,197,94,0.06)", borderRadius: 8, padding: "10px 12px",
                  fontSize: 13, color: "var(--text)", border: "1px solid rgba(34,197,94,0.2)",
                  borderLeft: "3px solid var(--success)",
                }}
              >
                {pedido.mensagem_cliente}
              </div>
            </section>
          )}

          {/* Histórico da conversa */}
          {pedido.conversation_messages && pedido.conversation_messages.length > 0 && (
            <section>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
                Histórico da Conversa ({pedido.conversation_messages.length} mensagens)
              </div>
              <div
                style={{
                  display: "flex", flexDirection: "column", gap: 6,
                  maxHeight: 260, overflowY: "auto",
                  background: "var(--surface2)", borderRadius: 10,
                  padding: "10px 12px", border: "1px solid var(--border)",
                }}
              >
                {pedido.conversation_messages.map((msg, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex", gap: 8, alignItems: "flex-start",
                      flexDirection: msg.role === "user" ? "row" : "row-reverse",
                    }}
                  >
                    <div
                      style={{
                        width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
                        background: msg.role === "user" ? "var(--success)" : "var(--accent)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 10, fontWeight: 700, color: "#fff",
                      }}
                    >
                      {msg.role === "user" ? "C" : "M"}
                    </div>
                    <div
                      style={{
                        background: msg.role === "user" ? "var(--surface)" : "rgba(99,102,241,0.1)",
                        border: `1px solid ${msg.role === "user" ? "var(--border)" : "rgba(99,102,241,0.2)"}`,
                        borderRadius: 8, padding: "6px 10px",
                        fontSize: 12, color: "var(--text)", maxWidth: "75%",
                      }}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Actions footer */}
        {pedido.status !== "pedido_feito" && pedido.status !== "cancelado" && (
          <div
            style={{
              padding: "14px 20px", borderTop: "1px solid var(--border)",
              display: "flex", gap: 10, justifyContent: "flex-end",
            }}
          >
            {editing ? (
              <>
                <button
                  onClick={() => {
                    setEditItems(pedido.itens_json.map((item) => ({ ...item })));
                    setEditObservacoes(pedido.observacoes || "");
                    setEditing(false);
                  }}
                  disabled={loading}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    background: "transparent", color: "var(--muted)",
                    border: "1px solid var(--border)", borderRadius: 8,
                    padding: "8px 16px", fontSize: 13, fontWeight: 600,
                    cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
                  }}
                >
                  Cancelar edição
                </button>
                <button
                  onClick={saveEdit}
                  disabled={loading}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    background: "var(--accent)", color: "#fff",
                    border: "none", borderRadius: 8,
                    padding: "8px 16px", fontSize: 13, fontWeight: 700,
                    cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
                  }}
                >
                  {loading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={14} />}
                  Salvar edição
                </button>
              </>
            ) : (
              <button
                onClick={() => setEditing(true)}
                disabled={loading}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  background: "rgba(99,102,241,0.1)", color: "var(--accent)",
                  border: "1px solid rgba(99,102,241,0.3)", borderRadius: 8,
                  padding: "8px 16px", fontSize: 13, fontWeight: 600,
                  cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
                }}
              >
                <Pencil size={14} />
                Editar Pedido
              </button>
            )}
            <button
              onClick={() => onSetStatus("cancelado")}
              disabled={loading}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "rgba(239,68,68,0.08)", color: "var(--error)",
                border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8,
                padding: "8px 16px", fontSize: 13, fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
              }}
            >
              <XCircle size={14} />
              Cancelar Pedido
            </button>
            <button
              onClick={() => onSetStatus("pedido_feito")}
              disabled={loading}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "var(--success)", color: "#fff",
                border: "none", borderRadius: 8,
                padding: "8px 20px", fontSize: 13, fontWeight: 700,
                cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
              }}
            >
              {loading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <CheckCircle2 size={14} />}
              Marcar como Feito
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pedido Card
// ---------------------------------------------------------------------------

function PedidoCard({
  pedido,
  onClick,
}: {
  pedido: PedidoRevisao;
  onClick: () => void;
}) {
  const color = STATUS_COLOR[pedido.status];

  return (
    <div
      onClick={onClick}
      style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 12, padding: "14px 16px",
        cursor: "pointer", transition: "border-color 0.15s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--accent)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text)" }}>
            {pedido.cliente_nome || "Cliente"}
          </div>
          <div style={{ fontSize: 11, color: "var(--accent)", marginTop: 2, fontWeight: 700 }}>
            {pedidoProtocolo(pedido)}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2, display: "flex", alignItems: "center", gap: 4 }}>
            <Phone size={10} />
            {fmtPhone(pedido.cliente_telefone)}
          </div>
        </div>
        <span
          style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 5, whiteSpace: "nowrap",
            color, background: `${color}18`, border: `1px solid ${color}40`,
          }}
        >
          {STATUS_LABEL[pedido.status]}
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 10 }}>
        {pedido.itens_json.slice(0, 3).map((item, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text)" }}>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "70%" }}>{itemNome(item)}</span>
            <span style={{ color: "var(--accent)", fontWeight: 600, flexShrink: 0 }}>{itemQuantidade(item)}</span>
          </div>
        ))}
        {pedido.itens_json.length > 3 && (
          <span style={{ fontSize: 11, color: "var(--muted)" }}>+{pedido.itens_json.length - 3} item(s)</span>
        )}
      </div>

      <div style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 4 }}>
        <Clock size={10} />
        {fmtDate(pedido.created_at)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const TABS: { key: PedidoRevisaoStatus | "todos"; label: string }[] = [
  { key: "todos", label: "Todos" },
  { key: "pendente", label: "Pendentes" },
  { key: "pedido_feito", label: "Feitos" },
  { key: "cancelado", label: "Cancelados" },
];

export default function RevisaoPedidoPage() {
  const [data, setData] = useState<PedidoRevisaoListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<PedidoRevisaoStatus | "todos">("pendente");
  const [selected, setSelected] = useState<PedidoRevisao | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [produtos, setProdutos] = useState<Produto[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = activeTab === "todos" ? undefined : activeTab;
      const result = await revisaoPedidoApi.list(status);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar pedidos");
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => { load(); }, [load]);

  const loadProdutos = useCallback(async () => {
    try {
      const result = await produtosApi.list();
      setProdutos(result.produtos ?? []);
    } catch (err) {
      console.error("Erro ao carregar produtos para edição de pedido", err);
    }
  }, []);

  useEffect(() => { loadProdutos(); }, [loadProdutos]);

  async function handleSetStatus(status: PedidoRevisaoStatus) {
    if (!selected) return;
    setActionLoading(true);
    try {
      const updated = await revisaoPedidoApi.setStatus(selected.id, status);
      setSelected(updated);
      load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleUpdatePedido(payload: { itens_json: PedidoRevisaoItem[]; observacoes: string }) {
    if (!selected) return;
    setActionLoading(true);
    try {
      const updated = await revisaoPedidoApi.update(selected.id, payload);
      setSelected(updated);
      load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao editar pedido");
    } finally {
      setActionLoading(false);
    }
  }

  const stats = data?.stats;
  const pedidos = data?.pedidos ?? [];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Revisão de Pedidos" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>

        {/* Stats row */}
        {stats && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 14, marginBottom: 24 }}>
            {(["pendente", "pedido_feito", "cancelado"] as PedidoRevisaoStatus[]).map((s) => (
              <div
                key={s}
                onClick={() => setActiveTab(s)}
                style={{
                  background: "var(--surface)", border: `1px solid ${activeTab === s ? STATUS_COLOR[s] : "var(--border)"}`,
                  borderRadius: 12, padding: "14px 18px", cursor: "pointer",
                }}
              >
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
                  {STATUS_LABEL[s]}
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color: STATUS_COLOR[s] }}>
                  {stats[s]}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs + refresh */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
          <div style={{ display: "flex", gap: 4 }}>
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: "7px 16px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                  cursor: "pointer", border: "none",
                  background: activeTab === tab.key ? "var(--accent)" : "var(--surface2)",
                  color: activeTab === tab.key ? "#fff" : "var(--muted)",
                }}
              >
                {tab.label}
                {tab.key !== "todos" && stats && stats[tab.key as PedidoRevisaoStatus] > 0 && (
                  <span
                    style={{
                      marginLeft: 6, background: activeTab === tab.key ? "rgba(255,255,255,0.25)" : STATUS_COLOR[tab.key as PedidoRevisaoStatus],
                      color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 10, fontWeight: 700,
                    }}
                  >
                    {stats[tab.key as PedidoRevisaoStatus]}
                  </span>
                )}
              </button>
            ))}
          </div>
          <button
            onClick={load}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 600,
              color: "var(--text)", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            Atualizar
          </button>
        </div>

        {error && (
          <div style={{ color: "var(--error)", fontSize: 13, marginBottom: 16 }}>{error}</div>
        )}

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)", padding: "20px 0" }}>
            <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: 13 }}>Carregando pedidos...</span>
          </div>
        )}

        {!loading && pedidos.length === 0 && (
          <div
            style={{
              background: "var(--surface)", border: "1px dashed var(--border)",
              borderRadius: 14, padding: "48px 24px",
              textAlign: "center", color: "var(--muted)", fontSize: 13,
              display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
            }}
          >
            <Package size={28} color="var(--muted)" />
            {activeTab === "pendente"
              ? "Nenhum pedido aguardando revisão."
              : `Nenhum pedido com status "${STATUS_LABEL[activeTab as PedidoRevisaoStatus] ?? activeTab}".`}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
          {pedidos.map((p) => (
            <PedidoCard key={p.id} pedido={p} onClick={() => setSelected(p)} />
          ))}
        </div>

      </div>

      {selected && (
        <DetailModal
          pedido={selected}
          produtos={produtos}
          onClose={() => setSelected(null)}
          onSetStatus={handleSetStatus}
          onUpdate={handleUpdatePedido}
          loading={actionLoading}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

