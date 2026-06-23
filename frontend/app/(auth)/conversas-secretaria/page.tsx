"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, Bot, Clock, MessageSquareText, RefreshCw, Search, UserRound } from "lucide-react";
import Header from "@/components/layout/Header";
import { secretariaApi } from "@/lib/api";
import type { SecretaryConversation, SecretaryConversationDetail, SecretaryMessage } from "@/lib/types";

function fmtDateTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function stateCustomer(state: Record<string, unknown> | undefined) {
  const customer = state?.customer;
  if (!customer || typeof customer !== "object") return null;
  return customer as { code?: string; name?: string; document?: string; price_table_code?: string };
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const content = useMemo(() => JSON.stringify(value ?? null, null, 2), [value]);
  return (
    <section>
      <h3 style={{ margin: "0 0 8px", color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {title}
      </h3>
      <pre
        style={{
          margin: 0,
          padding: 12,
          maxHeight: 260,
          overflow: "auto",
          border: "1px solid var(--border)",
          borderRadius: 8,
          background: "#080910",
          color: "var(--text)",
          fontSize: 12,
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {content}
      </pre>
    </section>
  );
}

function MessageBubble({ message }: { message: SecretaryMessage }) {
  const isUser = message.role === "user";
  const Icon = isUser ? UserRound : Bot;
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 12,
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isUser ? "1fr 28px" : "28px 1fr",
          gap: 8,
          alignItems: "end",
          maxWidth: "min(760px, 88%)",
        }}
      >
        {!isUser && (
          <span style={{ width: 28, height: 28, display: "grid", placeItems: "center", borderRadius: 8, background: "var(--surface2)", color: "var(--accent)" }}>
            <Icon size={15} />
          </span>
        )}
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "10px 12px",
            background: isUser ? "rgba(59,130,246,0.16)" : "var(--surface2)",
            color: "var(--text)",
            overflowWrap: "anywhere",
            whiteSpace: "pre-wrap",
          }}
        >
          <div style={{ fontSize: 13, lineHeight: 1.55 }}>{message.content || ""}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 8, color: "var(--muted)", fontSize: 10 }}>
            <Clock size={11} />
            {fmtDateTime(message.created_at)}
          </div>
        </div>
        {isUser && (
          <span style={{ width: 28, height: 28, display: "grid", placeItems: "center", borderRadius: 8, background: "var(--accent)", color: "#fff" }}>
            <Icon size={15} />
          </span>
        )}
      </div>
    </div>
  );
}

export default function ConversasSecretariaPage() {
  const [conversations, setConversations] = useState<SecretaryConversation[]>([]);
  const [detail, setDetail] = useState<SecretaryConversationDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await secretariaApi.listConversations({
        search: search || undefined,
        page,
        pageSize: 30,
      });
      setConversations(result.conversations);
      setPages(result.pages);
      setTotal(result.total);
      if (!selectedId && result.conversations[0]?.id) {
        setSelectedId(result.conversations[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar conversas");
    } finally {
      setLoading(false);
    }
  }, [page, search, selectedId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setDetailLoading(true);
    secretariaApi
      .getConversation(selectedId)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Falha ao abrir conversa");
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selectedState = detail?.conversation.state_json || {};
  const selectedCustomer = stateCustomer(selectedState);

  return (
    <>
      <Header />
      <main style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", padding: 24, overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", marginBottom: 16 }}>
          <div>
            <h1 style={{ margin: 0, color: "var(--text)", fontSize: 24 }}>Conversas Secretaria</h1>
            <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 13 }}>
              Historico das mensagens recebidas, respostas enviadas e estado atual do fluxo.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              height: 38,
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--surface2)",
              color: "var(--text)",
              padding: "0 12px",
              cursor: "pointer",
            }}
          >
            <RefreshCw size={15} />
            Atualizar
          </button>
        </div>

        {error && (
          <div style={{ marginBottom: 14, border: "1px solid var(--error)", borderRadius: 8, padding: 12, color: "var(--error)", background: "rgba(248,113,113,0.08)" }}>
            {error}
          </div>
        )}

        <section style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "360px minmax(0, 1fr)", gap: 16 }}>
          <aside style={{ minHeight: 0, border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
              <label style={{ display: "block", position: "relative" }}>
                <Search size={16} style={{ position: "absolute", left: 11, top: 11, color: "var(--muted)" }} />
                <input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(1);
                  }}
                  placeholder="Buscar telefone, instancia, cliente..."
                  style={{
                    width: "100%",
                    height: 38,
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "var(--surface2)",
                    color: "var(--text)",
                    padding: "0 12px 0 36px",
                  }}
                />
              </label>
              <div style={{ marginTop: 8, color: "var(--muted)", fontSize: 11 }}>{total} conversa(s)</div>
            </div>

            <div style={{ overflow: "auto", minHeight: 0 }}>
              {loading && <div style={{ padding: 18, color: "var(--muted)" }}>Carregando conversas...</div>}
              {!loading && conversations.length === 0 && <div style={{ padding: 18, color: "var(--muted)" }}>Nenhuma conversa encontrada.</div>}
              {!loading &&
                conversations.map((conversation) => {
                  const customer = stateCustomer(conversation.state_json);
                  const active = conversation.id === selectedId;
                  return (
                    <button
                      key={conversation.id}
                      onClick={() => setSelectedId(conversation.id)}
                      style={{
                        width: "100%",
                        textAlign: "left",
                        display: "grid",
                        gap: 6,
                        padding: 12,
                        border: 0,
                        borderBottom: "1px solid var(--border)",
                        background: active ? "rgba(59,130,246,0.14)" : "transparent",
                        color: "var(--text)",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <strong style={{ fontSize: 13 }}>{conversation.representative_phone}</strong>
                        <span style={{ color: "var(--muted)", fontSize: 10 }}>{fmtDateTime(conversation.updated_at)}</span>
                      </div>
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>
                        {conversation.instance_name} · Rep. {conversation.cod_rep}
                      </div>
                      {customer && (
                        <div style={{ color: "var(--text)", fontSize: 12 }}>
                          Cliente {customer.code || "-"} · {customer.name || "-"}
                        </div>
                      )}
                      <div style={{ color: "var(--muted)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {conversation.latest_message?.content || "Sem mensagens"}
                      </div>
                      {conversation.error_hint && (
                        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--error)", fontSize: 11 }}>
                          <AlertCircle size={12} />
                          Pendencia no fluxo
                        </div>
                      )}
                    </button>
                  );
                })}
            </div>

            {pages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: 10, borderTop: "1px solid var(--border)" }}>
                <button onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1} style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface2)", color: "var(--text)", padding: "7px 10px" }}>
                  Anterior
                </button>
                <span style={{ color: "var(--muted)", fontSize: 12 }}>{page}/{pages}</span>
                <button onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages} style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface2)", color: "var(--text)", padding: "7px 10px" }}>
                  Proxima
                </button>
              </div>
            )}
          </aside>

          <section style={{ minHeight: 0, display: "grid", gridTemplateRows: "auto minmax(0, 1fr)", border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", overflow: "hidden" }}>
            <header style={{ padding: 14, borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 12, marginBottom: 6 }}>
                  <MessageSquareText size={15} />
                  {detail?.conversation.instance_name || "-"} · {detail?.conversation.representative_phone || "-"}
                </div>
                <h2 style={{ margin: 0, color: "var(--text)", fontSize: 17 }}>
                  {selectedCustomer ? `${selectedCustomer.code || ""} ${selectedCustomer.name || ""}`.trim() : "Conversa da secretaria"}
                </h2>
              </div>
              <div style={{ color: "var(--muted)", fontSize: 12, textAlign: "right" }}>
                <div>Atualizado</div>
                <strong style={{ color: "var(--text)" }}>{fmtDateTime(detail?.conversation.updated_at)}</strong>
              </div>
            </header>

            <div style={{ minHeight: 0, overflow: "auto", display: "grid", gridTemplateColumns: "minmax(0, 1fr) 340px" }}>
              <div style={{ padding: 16, minWidth: 0 }}>
                {detailLoading && <div style={{ color: "var(--muted)" }}>Abrindo conversa...</div>}
                {!detailLoading && !detail && <div style={{ color: "var(--muted)" }}>Selecione uma conversa.</div>}
                {!detailLoading && detail?.messages.map((message) => <MessageBubble key={message.id} message={message} />)}
              </div>

              <aside style={{ borderLeft: "1px solid var(--border)", padding: 14, overflow: "auto", display: "grid", gap: 14, alignContent: "start", background: "rgba(255,255,255,0.015)" }}>
                {detail?.error_hint && (
                  <div style={{ border: "1px solid var(--error)", borderRadius: 8, padding: 10, background: "rgba(248,113,113,0.08)", color: "var(--error)", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {detail.error_hint}
                  </div>
                )}

                <section>
                  <h3 style={{ margin: "0 0 8px", color: "var(--muted)", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5 }}>Pedidos vinculados</h3>
                  {!detail?.orders?.length && <div style={{ color: "var(--muted)", fontSize: 12 }}>Nenhum pedido salvo nessa conversa.</div>}
                  {detail?.orders?.map((order) => (
                    <div key={order.id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                        <strong style={{ color: "var(--text)", fontSize: 12 }}>{order.protocol}</strong>
                        <span style={{ color: order.status === "failed" ? "var(--error)" : "var(--muted)", fontSize: 11 }}>{order.status}</span>
                      </div>
                      <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 5 }}>
                        Cliente {order.customer_code || "-"} · R$ {Number(order.total || 0).toFixed(2)}
                      </div>
                      {order.error_message && <div style={{ color: "var(--error)", fontSize: 11, marginTop: 6 }}>{order.error_message}</div>}
                    </div>
                  ))}
                </section>

                <JsonBlock title="Estado do fluxo" value={selectedState} />
              </aside>
            </div>
          </section>
        </section>
      </main>
    </>
  );
}
