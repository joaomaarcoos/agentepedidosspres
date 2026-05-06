"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, Bot, CheckCircle2, ChevronLeft, ChevronRight,
  MessageSquare, Play, RefreshCw, Repeat2, Send, X,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { recorrenciaApi } from "@/lib/api";
import type {
  RecorrenciaOverview, RecorrenciaTarget, RecorrenciaStatus,
} from "@/lib/types";

// ─── helpers ─────────────────────────────────────────────────────────────────

const TIER_LABEL: Record<string, string> = {
  media: "Média",
  alta: "Alta",
  semanal_forte: "Semanal",
};

const TIER_COLOR: Record<string, string> = {
  media: "var(--muted)",
  alta: "var(--warn)",
  semanal_forte: "var(--error)",
};

const STATUS_LABEL: Record<RecorrenciaStatus, string> = {
  candidate: "Candidato",
  ai_approved: "IA Aprovado",
  ai_rejected: "IA Rejeitado",
  dispatched: "Disparado",
  responded: "Respondeu",
  converted: "Convertido",
  opted_out: "Opt-out",
};

const STATUS_COLOR: Record<RecorrenciaStatus, string> = {
  candidate: "var(--muted)",
  ai_approved: "var(--accent)",
  ai_rejected: "var(--error)",
  dispatched: "var(--warn)",
  responded: "var(--success)",
  converted: "var(--success)",
  opted_out: "var(--muted)",
};

const STATUS_TABS: { key: string; label: string }[] = [
  { key: "", label: "Todos" },
  { key: "candidate", label: "Candidatos" },
  { key: "ai_approved", label: "IA Aprovados" },
  { key: "ai_rejected", label: "IA Rejeitados" },
  { key: "dispatched", label: "Disparados" },
  { key: "responded", label: "Responderam" },
  { key: "converted", label: "Convertidos" },
];

function StatusBadge({ status }: { status: RecorrenciaStatus }) {
  const color = STATUS_COLOR[status] ?? "var(--muted)";
  return (
    <span style={{
      padding: "3px 9px", borderRadius: 999,
      background: `${color}18`, color,
      border: `1px solid ${color}44`,
      fontSize: 11, fontWeight: 700, textTransform: "uppercase",
      whiteSpace: "nowrap",
    }}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function TierBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span style={{ color: "var(--muted)" }}>—</span>;
  const color = TIER_COLOR[tier] ?? "var(--muted)";
  return (
    <span style={{ color, fontWeight: 700, fontSize: 12 }}>
      {TIER_LABEL[tier] ?? tier}
    </span>
  );
}

// ─── drawer de detalhe ───────────────────────────────────────────────────────

function DetailDrawer({ data, onClose }: { data: RecorrenciaTarget; onClose: () => void }) {
  let aiData: Record<string, unknown> | null = null;
  try {
    if (data.ai_reasoning) aiData = JSON.parse(data.ai_reasoning);
  } catch { /* ignore */ }

  const mensagem = aiData?.mensagem as string | undefined;
  const pedidoSugerido = aiData?.pedido_sugerido as { codPro: string; desPro: string; qtdPed: number }[] | undefined;

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0,
        background: "rgba(0,0,0,0.45)", zIndex: 100, backdropFilter: "blur(2px)",
      }} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(680px, 94vw)",
        background: "var(--surface)", borderLeft: "1px solid var(--border)",
        zIndex: 101, display: "flex", flexDirection: "column",
      }}>
        {/* header */}
        <div style={{
          padding: "20px 24px", borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 18, fontWeight: 800, color: "var(--text)" }}>
                {data.customer_name || "—"}
              </span>
              <StatusBadge status={data.status} />
            </div>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              {data.cpf_cnpj} · {data.customer_phone || "sem telefone"}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: "1px solid var(--border)",
            borderRadius: 8, padding: "6px 8px", cursor: "pointer", color: "var(--muted)",
          }}>
            <X size={15} />
          </button>
        </div>

        <div style={{ padding: 24, overflow: "auto", display: "grid", gap: 16 }}>
          {/* métricas */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              ["Tier", data.recurrence_tier ? TIER_LABEL[data.recurrence_tier] : "—"],
              ["Pedidos 30d", String(data.orders_count_30d ?? "—")],
              ["Intervalo médio", data.recurrence_interval_days != null ? `${data.recurrence_interval_days}d` : "—"],
              ["Último pedido", data.last_order_date || "—"],
              ["Próximo previsto", data.predicted_next_order_date || "—"],
              ["Dias p/ janela", data.days_until_predicted != null ? String(data.days_until_predicted) : "—"],
            ].map(([label, value]) => (
              <div key={label} style={{
                background: "var(--surface2)", border: "1px solid var(--border)",
                borderRadius: 10, padding: "12px 14px",
              }}>
                <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{value}</div>
              </div>
            ))}
          </div>

          {/* decisão IA */}
          {aiData && (
            <div style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 12, padding: 16,
            }}>
              <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 10 }}>
                Decisão da IA
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                <span style={{
                  padding: "4px 10px", borderRadius: 999, fontSize: 12, fontWeight: 700,
                  background: data.ai_decision === "sim" ? "var(--success)22" : "var(--error)22",
                  color: data.ai_decision === "sim" ? "var(--success)" : "var(--error)",
                  border: `1px solid ${data.ai_decision === "sim" ? "var(--success)44" : "var(--error)44"}`,
                }}>
                  {data.ai_decision === "sim" ? "✓ Aprovado" : "✗ Rejeitado"}
                </span>
                {(aiData.nivel_confianca as string) && (
                  <span style={{ fontSize: 12, color: "var(--muted)", alignSelf: "center" }}>
                    Confiança: {String(aiData.nivel_confianca)}
                  </span>
                )}
              </div>
              {(aiData.motivo as string) && (
                <p style={{ fontSize: 13, color: "var(--text)", margin: 0 }}>
                  {String(aiData.motivo)}
                </p>
              )}
            </div>
          )}

          {/* mensagem gerada */}
          {mensagem && (
            <div style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 12, overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 6 }}>
                <MessageSquare size={13} color="var(--accent)" />
                <span style={{ fontWeight: 700, fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Mensagem gerada
                </span>
              </div>
              <div style={{ padding: 16 }}>
                <pre style={{ margin: 0, fontFamily: "inherit", fontSize: 13, color: "var(--text)", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
                  {mensagem}
                </pre>
              </div>
            </div>
          )}

          {/* pedido sugerido */}
          {pedidoSugerido && pedidoSugerido.length > 0 && (
            <div style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 12, overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 700, fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Pedido sugerido
                </span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {["Código", "Produto", "Qtd"].map(h => (
                      <th key={h} style={{ padding: "8px 14px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pedidoSugerido.map((item, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                      <td style={{ padding: "8px 14px", color: "var(--accent)", fontWeight: 700, fontSize: 12 }}>{item.codPro}</td>
                      <td style={{ padding: "8px 14px", color: "var(--text)", fontSize: 13 }}>{item.desPro}</td>
                      <td style={{ padding: "8px 14px", color: "var(--text)", fontSize: 13 }}>{item.qtdPed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* últimos 3 pedidos */}
          {(data.last_3_orders_json ?? []).length > 0 && (
            <div style={{
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 12, overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 700, fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6 }}>
                  Últimos pedidos
                </span>
              </div>
              {(data.last_3_orders_json ?? []).map((p, i) => (
                <div key={i} style={{ padding: "12px 16px", borderTop: i > 0 ? "1px solid var(--border)" : undefined }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontWeight: 700, color: "var(--accent)", fontSize: 13 }}>#{p.numero}</span>
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>{p.data} · R$ {p.valor_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                  </div>
                  {(p.itens ?? []).map((it, j) => (
                    <div key={j} style={{ fontSize: 12, color: "var(--muted)", paddingLeft: 8 }}>
                      {it.desPro || it.codPro} — {it.qtdPed}un · R$ {it.vlrTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ─── página principal ────────────────────────────────────────────────────────

export default function RecorrenciaPage() {
  const [activeStatus, setActiveStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<RecorrenciaOverview | null>(null);
  const [selected, setSelected] = useState<RecorrenciaTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [validating, setValidating] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "error" | "success" } | null>(null);

  const load = useCallback(async (targetPage = 1, status = activeStatus) => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.list({
        status: status || undefined,
        page: targetPage,
      });
      setData(result);
      setPage(targetPage);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao carregar", type: "error" });
    } finally {
      setLoading(false);
    }
  }, [activeStatus]);

  useEffect(() => { load(1, activeStatus); }, [activeStatus]);

  const handleRunScript = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.runScript();
      setMessage({
        text: `Script concluído: ${result.inserted_or_updated} candidatos atualizados, ${result.errors.length} erros`,
        type: result.errors.length > 0 ? "error" : "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao rodar script", type: "error" });
    } finally {
      setRunning(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.validate({ limit: 20 });
      setMessage({
        text: `IA: ${result.approved} aprovados, ${result.rejected} rejeitados`,
        type: "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao validar", type: "error" });
    } finally {
      setValidating(false);
    }
  };

  const openDetail = async (id: string) => {
    try {
      const detail = await recorrenciaApi.detail(id);
      setSelected(detail);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao abrir detalhe", type: "error" });
    }
  };

  const stats = data?.stats;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Recompra — Pipeline de Recorrência" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>

        {/* ações */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
          <button
            onClick={handleRunScript}
            disabled={running || loading}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--surface2)", color: "var(--text)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 16px", fontWeight: 600, fontSize: 13,
              cursor: running ? "not-allowed" : "pointer", opacity: running ? 0.7 : 1,
            }}
          >
            <Play size={13} style={{ animation: running ? "spin 1s linear infinite" : undefined }} />
            {running ? "Rodando..." : "Rodar Script"}
          </button>

          <button
            onClick={handleValidate}
            disabled={validating || loading}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--accent)", color: "#fff",
              border: "none", borderRadius: 8,
              padding: "8px 16px", fontWeight: 600, fontSize: 13,
              cursor: validating ? "not-allowed" : "pointer", opacity: validating ? 0.7 : 1,
            }}
          >
            <Bot size={13} style={{ animation: validating ? "spin 1s linear infinite" : undefined }} />
            {validating ? "Validando..." : "Validar com IA"}
          </button>

          <button
            onClick={() => load(1, activeStatus)}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "transparent", color: "var(--muted)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 12px", fontSize: 13, cursor: "pointer",
            }}
          >
            <RefreshCw size={13} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
          </button>

          {message && (
            <span style={{ fontSize: 12, color: message.type === "error" ? "var(--error)" : "var(--success)" }}>
              {message.text}
            </span>
          )}
        </div>

        {/* stats cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14, marginBottom: 24 }}>
          {[
            { label: "Candidatos", value: stats?.candidate ?? 0, icon: Repeat2, color: "var(--muted)" },
            { label: "IA Aprovados", value: stats?.ai_approved ?? 0, icon: CheckCircle2, color: "var(--accent)" },
            { label: "Disparados", value: stats?.dispatched ?? 0, icon: Send, color: "var(--warn)" },
            { label: "Convertidos", value: stats?.converted ?? 0, icon: AlertTriangle, color: "var(--success)" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} style={{
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 12, padding: "16px 20px",
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  {label}
                </span>
                <Icon size={15} color={color} />
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>{value}</div>
            </div>
          ))}
        </div>

        {/* tabs de status */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, flexWrap: "wrap" }}>
          {STATUS_TABS.map(({ key, label }) => {
            const isActive = activeStatus === key;
            return (
              <button
                key={key}
                onClick={() => { setActiveStatus(key); setPage(1); }}
                style={{
                  padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                  cursor: "pointer", border: "1px solid var(--border)",
                  background: isActive ? "var(--accent)" : "var(--surface2)",
                  color: isActive ? "#fff" : "var(--muted)",
                  transition: "all 0.15s",
                }}
              >
                {label}
                {key && stats && (
                  <span style={{ marginLeft: 6, opacity: 0.75 }}>
                    {stats[key as keyof typeof stats] ?? 0}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* tabela */}
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 16, overflow: "hidden",
        }}>
          <div style={{
            padding: "14px 20px", borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
              Mapa de Recompra
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              {data?.total ?? 0} registros
            </span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : !data || data.targets.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhum registro encontrado. Rode o script para gerar candidatos.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Cliente", "Status", "Tier", "Pedidos 30d", "Último pedido", "Próximo previsto", "Dias janela"].map(h => (
                      <th key={h} style={{
                        padding: "10px 16px", textAlign: "left",
                        fontSize: 11, fontWeight: 700, color: "var(--muted)",
                        textTransform: "uppercase", letterSpacing: 0.5,
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.targets.map(t => (
                    <tr
                      key={t.id}
                      onClick={() => openDetail(t.id)}
                      style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
                      onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = "var(--surface2)"}
                      onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = "transparent"}
                    >
                      <td style={{ padding: "10px 16px" }}>
                        <div style={{ color: "var(--text)", fontWeight: 700, fontSize: 13 }}>
                          {t.customer_name || "—"}
                        </div>
                        <div style={{ color: "var(--muted)", fontSize: 11 }}>{t.cpf_cnpj}</div>
                      </td>
                      <td style={{ padding: "10px 16px" }}>
                        <StatusBadge status={t.status} />
                      </td>
                      <td style={{ padding: "10px 16px" }}>
                        <TierBadge tier={t.recurrence_tier} />
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)", fontWeight: 700 }}>
                        {t.orders_count_30d ?? "—"}
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        {t.last_order_date || "—"}
                      </td>
                      <td style={{ padding: "10px 16px", color: "var(--text)" }}>
                        {t.predicted_next_order_date || "—"}
                      </td>
                      <td style={{
                        padding: "10px 16px", fontWeight: 700,
                        color: t.days_until_predicted != null && t.days_until_predicted <= 0
                          ? "var(--error)"
                          : t.days_until_predicted != null && t.days_until_predicted <= 2
                            ? "var(--warn)"
                            : "var(--muted)",
                      }}>
                        {t.days_until_predicted != null ? `${t.days_until_predicted}d` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(data?.pages ?? 1) > 1 && (
            <div style={{
              padding: "12px 20px", borderTop: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Página {page} de {data?.pages}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => load(page - 1, activeStatus)}
                  disabled={page <= 1}
                  style={{
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    color: page <= 1 ? "var(--border)" : "var(--text)",
                    borderRadius: 6, padding: "5px 10px",
                    cursor: page <= 1 ? "not-allowed" : "pointer",
                  }}
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  onClick={() => load(page + 1, activeStatus)}
                  disabled={page >= (data?.pages ?? 1)}
                  style={{
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    color: page >= (data?.pages ?? 1) ? "var(--border)" : "var(--text)",
                    borderRadius: 6, padding: "5px 10px",
                    cursor: page >= (data?.pages ?? 1) ? "not-allowed" : "pointer",
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
