"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, Bot, CheckCircle2, ChevronLeft, ChevronRight,
  DollarSign, MessageSquare, Play, RefreshCw, Repeat2,
  Send, ShieldCheck, X, Zap, BellOff, Bell,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { recorrenciaApi, settingsApi } from "@/lib/api";
import type { RecorrenciaOverview, RecorrenciaTarget, RecorrenciaStatus } from "@/lib/types";

// ─── AI data parser ───────────────────────────────────────────────────────────

interface AiData {
  decisao?: string;
  nivel_confianca?: string;
  motivo?: string;
  pedido_sugerido?: Array<{ codPro: string; desPro: string; qtdPed: number }>;
  valor_medio?: number;
  mensagem?: string;
  tabela_preco?: string;
}

function parseAi(raw: string | null): AiData | null {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return { motivo: raw }; }
}

// ─── Constantes visuais ───────────────────────────────────────────────────────

const TIER_LABEL: Record<string, string> = {
  media: "Média", alta: "Alta", semanal_forte: "Semanal",
};

const TIER_COLOR: Record<string, string> = {
  media: "var(--muted)", alta: "var(--warn)", semanal_forte: "var(--error)",
};

const CONFIANCA_COLOR: Record<string, string> = {
  alto: "var(--success)", medio: "var(--warn)", baixo: "var(--error)",
};

const CONFIANCA_LABEL: Record<string, string> = {
  alto: "Alta", medio: "Média", baixo: "Baixa",
};

const STATUS_LABEL: Record<RecorrenciaStatus, string> = {
  candidate: "Candidato",
  ai_approved: "IA Aprovado",
  ai_rejected: "IA Rejeitado",
  needs_review: "Revisão",
  dispatched: "Disparado",
  responded: "Respondeu",
  converted: "Convertido",
  opted_out: "Opt-out",
  activation_candidate: "Ativação Candidato",
  activation_approved: "Ativação Aprovada",
  activation_rejected: "Ativação Rejeitada",
};

const STATUS_COLOR: Record<RecorrenciaStatus, string> = {
  candidate: "var(--muted)",
  ai_approved: "var(--accent)",
  ai_rejected: "var(--error)",
  needs_review: "var(--warn)",
  dispatched: "var(--warn)",
  responded: "var(--success)",
  converted: "var(--success)",
  opted_out: "var(--muted)",
  activation_candidate: "var(--muted)",
  activation_approved: "var(--accent)",
  activation_rejected: "var(--error)",
};

const STATUS_TABS: { key: string; label: string }[] = [
  { key: "", label: "Todos" },
  { key: "candidate", label: "Candidatos" },
  { key: "ai_approved", label: "IA Aprovados" },
  { key: "needs_review", label: "Revisão" },
  { key: "ai_rejected", label: "Rejeitados" },
  { key: "dispatched", label: "Disparados" },
  { key: "responded", label: "Responderam" },
  { key: "converted", label: "Convertidos" },
];

// ─── Helpers de janela ────────────────────────────────────────────────────────

function janelaHeat(days: number | null): { color: string; label: string; hot: boolean } {
  if (days === null) return { color: "var(--muted)", label: "—", hot: false };
  const label = days === 0 ? "HOJE" : days > 0 ? `+${days}d` : `${days}d`;
  if (days >= -2 && days <= 2) return { color: "var(--success)", label, hot: true };
  if (days >= -7) return { color: "var(--warn)", label, hot: false };
  return { color: "var(--muted)", label, hot: false };
}

function pedidoInline(ai: AiData | null): string {
  const items = ai?.pedido_sugerido;
  if (!items?.length) return ai?.decisao === "sim" ? "contato genérico" : "—";
  const preview = items
    .slice(0, 2)
    .map(i => `${(i.desPro || i.codPro).split(" ").slice(0, 3).join(" ")} ×${i.qtdPed}`)
    .join(", ");
  return items.length > 2 ? `${preview} +${items.length - 2}` : preview;
}

function fmtBRL(value: number | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 0 });
}

// ─── Componentes menores ──────────────────────────────────────────────────────

function StatusBadge({ status }: { status: RecorrenciaStatus }) {
  const color = STATUS_COLOR[status] ?? "var(--muted)";
  return (
    <span style={{
      padding: "3px 9px", borderRadius: 999,
      background: `${color}18`, color,
      border: `1px solid ${color}44`,
      fontSize: 11, fontWeight: 700, textTransform: "uppercase", whiteSpace: "nowrap",
    }}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function TierBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span style={{ color: "var(--muted)" }}>—</span>;
  const color = TIER_COLOR[tier] ?? "var(--muted)";
  return <span style={{ color, fontWeight: 700, fontSize: 12 }}>{TIER_LABEL[tier] ?? tier}</span>;
}

function ConfiancaBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <span style={{ color: "var(--muted)", fontSize: 12 }}>—</span>;
  const color = CONFIANCA_COLOR[value] ?? "var(--muted)";
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}44`,
    }}>
      {CONFIANCA_LABEL[value] ?? value}
    </span>
  );
}

function JanelaBadge({ days }: { days: number | null }) {
  const { color, label, hot } = janelaHeat(days);
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "4px 10px", borderRadius: 8,
      background: `${color}18`, color,
      border: `1px solid ${color}44`,
      fontSize: 13, fontWeight: 800, whiteSpace: "nowrap",
      boxShadow: hot ? `0 0 0 2px ${color}33` : undefined,
    }}>
      {hot && (
        <span style={{
          width: 6, height: 6, borderRadius: "50%",
          background: color, display: "inline-block",
          animation: "pulse 1.5s ease-in-out infinite",
        }} />
      )}
      {label}
    </span>
  );
}

// ─── Drawer de detalhe ────────────────────────────────────────────────────────

function fmtDate(raw: string | null | undefined): string {
  if (!raw) return "—";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      padding: "0 0 9px", borderBottom: "1px solid var(--border)",
      display: "flex", alignItems: "center", gap: 8,
    }}>
      <span style={{
        fontSize: 10, fontWeight: 800, letterSpacing: 1,
        textTransform: "uppercase", color: "var(--muted)",
      }}>
        {children}
      </span>
    </div>
  );
}

function MetricCard({ label, value, color, wide }: { label: string; value: string; color?: string | null; wide?: boolean }) {
  return (
    <div style={{
      background: "var(--surface2)", border: "1px solid var(--border)",
      borderRadius: 10, padding: "12px 16px",
      gridColumn: wide ? "span 2" : undefined,
      minWidth: 0,
    }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 5 }}>
        {label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 800, color: color ?? "var(--text)", lineHeight: 1.2, wordBreak: "break-word" }}>
        {value}
      </div>
    </div>
  );
}

function DetailDrawer({ data, onClose }: { data: RecorrenciaTarget; onClose: () => void }) {
  const ai = parseAi(data.ai_reasoning);
  const { color: jColor, label: jLabel } = janelaHeat(data.days_until_predicted ?? null);
  const isApproved = data.ai_decision === "sim";
  const initials = (data.customer_name || "C").split(" ").slice(0, 2).map((w: string) => w[0]).join("").toUpperCase();

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(0,0,0,0.5)", zIndex: 100, backdropFilter: "blur(3px)",
        }}
      />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(760px, 96vw)",
        background: "var(--surface)", borderLeft: "1px solid var(--border)",
        zIndex: 101, display: "flex", flexDirection: "column",
        boxShadow: "-8px 0 40px rgba(0,0,0,0.35)",
      }}>

        {/* gradient top bar */}
        <div style={{
          background: isApproved
            ? "linear-gradient(135deg, #0d2818 0%, #0a1f13 100%)"
            : "linear-gradient(135deg, #1a1228 0%, #100d1a 100%)",
          padding: "24px 22px 20px",
          position: "relative",
          flexShrink: 0,
        }}>
          <button
            onClick={onClose}
            style={{
              position: "absolute", top: 16, right: 16,
              background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 8, padding: "6px 8px", cursor: "pointer",
              color: "rgba(255,255,255,0.7)", display: "flex", alignItems: "center", lineHeight: 0,
            }}
          >
            <X size={15} />
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
            <div style={{
              width: 50, height: 50, borderRadius: 14, flexShrink: 0,
              background: isApproved ? "rgba(34,197,94,0.2)" : "rgba(139,92,246,0.18)",
              border: `2px solid ${isApproved ? "rgba(34,197,94,0.4)" : "rgba(139,92,246,0.35)"}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 17, fontWeight: 800,
              color: isApproved ? "#4ade80" : "#a78bfa",
            }}>
              {initials}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 3 }}>
                {data.customer_name || "—"}
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {data.cpf_cnpj}
                {data.customer_phone && ` - ${data.customer_phone}`}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <StatusBadge status={data.status} />
            <JanelaBadge days={data.days_until_predicted ?? null} />
            {ai?.nivel_confianca && <ConfiancaBadge value={ai.nivel_confianca} />}
            {ai?.tabela_preco && (
              <span style={{
                fontSize: 11, fontWeight: 700, color: "var(--accent)",
                background: "var(--accent)15", border: "1px solid var(--accent)33",
                borderRadius: 6, padding: "2px 8px",
              }}>
                Tabela {ai.tabela_preco}
              </span>
            )}
          </div>
        </div>

        {/* conteúdo scrollável */}
        <div style={{ flex: 1, overflow: "auto", padding: "20px 22px", display: "flex", flexDirection: "column", gap: 18 }}>

          {/* métricas */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(155px, 1fr))", gap: 8 }}>
            <MetricCard label="Tier" value={data.recurrence_tier ? TIER_LABEL[data.recurrence_tier] : "—"} />
            <MetricCard label="Pedidos 30d" value={String(data.orders_count_30d ?? "—")} />
            <MetricCard label="Intervalo médio" value={data.recurrence_interval_days != null ? `${data.recurrence_interval_days}d` : "—"} />
            <MetricCard label="Último pedido" value={fmtDate(data.last_order_date)} />
            <MetricCard label="Próximo previsto" value={fmtDate(data.predicted_next_order_date)} />
            <MetricCard label="Janela" value={jLabel} color={jColor} />
            {ai?.valor_medio != null && ai.valor_medio > 0 && (
              <MetricCard label="Valor médio" value={fmtBRL(ai.valor_medio)} color="var(--accent)" wide />
            )}
          </div>

          {/* decisão IA */}
          {ai?.motivo && (
            <div style={{
              borderRadius: 12, overflow: "visible",
              border: `1px solid ${isApproved ? "var(--success)44" : "var(--border)"}`,
              background: isApproved ? "var(--success)08" : "var(--surface2)",
            }}>
              <SectionTitle>Análise da IA</SectionTitle>
              <div style={{ padding: "12px 18px" }}>
                <p style={{ margin: 0, fontSize: 13, color: "var(--text)", lineHeight: 1.65 }}>
                  {ai.motivo}
                </p>
              </div>
            </div>
          )}

          {/* mensagem pronta */}
          {ai?.mensagem && (
            <div style={{ borderRadius: 12, overflow: "visible", border: "1px solid var(--border)", background: "var(--surface2)" }}>
              <SectionTitle><MessageSquare size={11} style={{ display: "inline", marginRight: 5 }} />Mensagem WhatsApp</SectionTitle>
              <div style={{ padding: "14px 18px" }}>
                <div style={{ display: "flex" }}>
                  <div style={{
                    background: "#1a2a1a", border: "1px solid #2d4a2d",
                    borderRadius: "4px 12px 12px 12px",
                    padding: "12px 14px", maxWidth: "100%", minWidth: 0,
                  }}>
                    <p style={{
                      margin: 0, fontSize: 13, color: "#e8f5e8",
                      lineHeight: 1.6, whiteSpace: "pre-wrap", overflowWrap: "anywhere",
                    }}>
                      {ai.mensagem}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* pedido sugerido */}
          {(ai?.pedido_sugerido ?? []).length > 0 && (
            <div style={{ borderRadius: 12, overflow: "visible", border: "1px solid var(--border)", background: "var(--surface2)" }}>
              <SectionTitle>Pedido Sugerido</SectionTitle>
              <div style={{ padding: "8px 0" }}>
                {ai!.pedido_sugerido!.map((item, i) => (
                  <div key={i} style={{
                    display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(72px, auto)", alignItems: "center",
                    padding: "12px 18px", borderTop: i > 0 ? "1px solid var(--border)" : undefined,
                    gap: 12,
                  }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 700, marginBottom: 3, lineHeight: 1.35, wordBreak: "break-word" }}>
                        {item.desPro || item.codPro}
                      </div>
                      {item.codPro && (
                        <div style={{ fontSize: 11, color: "var(--accent)", fontFamily: "monospace" }}>{item.codPro}</div>
                      )}
                    </div>
                    <div style={{
                      flexShrink: 0, background: "var(--accent)18", border: "1px solid var(--accent)44",
                      borderRadius: 8, padding: "4px 12px",
                      fontSize: 13, fontWeight: 800, color: "var(--accent)", whiteSpace: "nowrap", justifySelf: "end",
                    }}>
                      {item.qtdPed} un
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* produtos recorrentes */}
          {(data.top_items_json ?? []).length > 0 && (
            <div style={{ borderRadius: 12, overflow: "visible", border: "1px solid var(--border)", background: "var(--surface2)" }}>
              <SectionTitle>Produtos Recorrentes</SectionTitle>
              <div style={{ padding: "8px 0" }}>
                {(data.top_items_json ?? []).map((item, i) => (
                  <div key={i} style={{
                    display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(160px, auto)", alignItems: "center",
                    padding: "12px 18px", borderTop: i > 0 ? "1px solid var(--border)" : undefined,
                    gap: 12,
                  }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 700, marginBottom: 3, lineHeight: 1.35, wordBreak: "break-word" }}>{item.desPro || item.codPro}</div>
                      {item.codPro && (
                        <div style={{ fontSize: 11, color: "var(--accent)", fontFamily: "monospace" }}>{item.codPro}</div>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
                      <span style={{
                        fontSize: 11, fontWeight: 700, color: "var(--warn)",
                        background: "var(--warn)15", border: "1px solid var(--warn)33",
                        borderRadius: 6, padding: "3px 8px",
                      }}>
                        {item.aparicoes}× pedidos
                      </span>
                      <span style={{
                        fontSize: 11, color: "var(--muted)",
                        background: "var(--surface)", border: "1px solid var(--border)",
                        borderRadius: 6, padding: "3px 8px",
                      }}>
                        {item.total_qtd} un
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* últimos pedidos */}
          {(data.last_3_orders_json ?? []).length > 0 && (
            <div style={{ borderRadius: 12, overflow: "visible", border: "1px solid var(--border)", background: "var(--surface2)" }}>
              <SectionTitle>Últimos Pedidos</SectionTitle>
              <div style={{ padding: "8px 0" }}>
                {(data.last_3_orders_json ?? []).map((p, i) => (
                  <div key={i} style={{ padding: "14px 18px", borderTop: i > 0 ? "1px solid var(--border)" : undefined }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <span style={{
                        fontSize: 12, fontWeight: 800, color: "var(--accent)",
                        background: "var(--accent)15", border: "1px solid var(--accent)33",
                        borderRadius: 6, padding: "3px 10px", fontFamily: "monospace",
                      }}>
                        #{p.numero}
                      </span>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
                          {p.valor_total.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--muted)" }}>{fmtDate(p.data)}</div>
                      </div>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {(p.itens ?? []).map((it, j) => (
                        <div key={j} style={{
                          display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(150px, auto)", alignItems: "center",
                          background: "var(--surface)", border: "1px solid var(--border)",
                          borderRadius: 7, padding: "8px 10px", gap: 10,
                        }}>
                          <span style={{ fontSize: 12, color: "var(--text)", minWidth: 0, lineHeight: 1.35, wordBreak: "break-word" }}>
                            {it.desPro || it.codPro}
                          </span>
                          <div style={{ flexShrink: 0, display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
                            <span style={{ fontSize: 11, color: "var(--muted)" }}>{it.qtdPed} un</span>
                            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)" }}>
                              {it.vlrTotal.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function RecorrenciaPage() {
  const [activeStatus, setActiveStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<RecorrenciaOverview | null>(null);
  const [selected, setSelected] = useState<RecorrenciaTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [validating, setValidating] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [pipelining, setPipelining] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "error" | "success" } | null>(null);
  const [disparoEnabled, setDisparoEnabled] = useState(true);
  const [togglingDisparo, setTogglingDisparo] = useState(false);

  const load = useCallback(async (targetPage = 1, status = activeStatus) => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.list({ status: status || undefined, page: targetPage });
      setData(result);
      setPage(targetPage);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao carregar", type: "error" });
    } finally {
      setLoading(false);
    }
  }, [activeStatus]);

  useEffect(() => { load(1, activeStatus); }, [activeStatus]);

  useEffect(() => {
    settingsApi.getDisparo()
      .then(s => setDisparoEnabled(s.disparo_recorrencia))
      .catch(() => {});
  }, []);

  const handleToggleDisparo = async () => {
    setTogglingDisparo(true);
    try {
      await settingsApi.setDisparo("disparo_recorrencia_enabled", !disparoEnabled);
      setDisparoEnabled(prev => !prev);
    } catch {
      setMessage({ text: "Falha ao alterar configuração de disparo", type: "error" });
    } finally {
      setTogglingDisparo(false);
    }
  };

  const handleRunScript = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.runScript();
      setMessage({
        text: `Script: ${result.inserted} inseridos, ${result.updated} atualizados, ${result.errors.length} erros`,
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
      const rev = result.needs_review ?? 0;
      setMessage({
        text: `IA: ${result.approved} aprovados, ${result.rejected} rejeitados${rev > 0 ? `, ${rev} em revisão` : ""}`,
        type: "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao validar", type: "error" });
    } finally {
      setValidating(false);
    }
  };

  const handleDispatch = async () => {
    if (!disparoEnabled) {
      setMessage({ text: "Disparo automático desativado. Ative o toggle para enviar mensagens.", type: "error" });
      return;
    }
    setDispatching(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.dispatch();
      setMessage({
        text: `Disparos: ${result.dispatched} enviados, ${result.skipped} pulados`,
        type: result.errors.length > 0 ? "error" : "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao disparar", type: "error" });
    } finally {
      setDispatching(false);
    }
  };

  const handlePipeline = async () => {
    setPipelining(true);
    setMessage(null);
    try {
      const result = await recorrenciaApi.pipeline("manual", false, !disparoEnabled);
      const d = result.dispatch;
      const dispatchNote = result.skip_dispatch ? " (disparo desativado)" : `, ${d.dispatched} disparados`;
      setMessage({
        text: `Pipeline completo — ${result.script.inserted} novos, ${result.validate.approved} aprovados${dispatchNote}`,
        type: "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha no pipeline", type: "error" });
    } finally {
      setPipelining(false);
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

  // Receita prevista: soma valor_medio dos targets aprovados visíveis na página atual
  const receitaPotencial = (data?.targets ?? [])
    .filter(t => t.ai_decision === "sim")
    .reduce((sum, t) => sum + (parseAi(t.ai_reasoning)?.valor_medio ?? 0), 0);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Pipeline de Recorrência" />

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
            onClick={handleDispatch}
            disabled={dispatching || loading || pipelining}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--surface2)", color: "var(--text)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 16px", fontWeight: 600, fontSize: 13,
              cursor: dispatching ? "not-allowed" : "pointer", opacity: dispatching ? 0.7 : 1,
            }}
          >
            <Send size={13} style={{ animation: dispatching ? "spin 1s linear infinite" : undefined }} />
            {dispatching ? "Disparando..." : "Disparar Recorrência"}
          </button>

          <button
            onClick={handlePipeline}
            disabled={pipelining || running || validating || dispatching}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--surface2)", color: "var(--text)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 16px", fontWeight: 600, fontSize: 13,
              cursor: pipelining ? "not-allowed" : "pointer", opacity: pipelining ? 0.7 : 1,
            }}
          >
            <Zap size={13} style={{ animation: pipelining ? "spin 1s linear infinite" : undefined }} />
            {pipelining ? "Executando..." : "Executar Pipeline"}
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

          {/* Toggle disparo automático */}
          <button
            onClick={handleToggleDisparo}
            disabled={togglingDisparo}
            title={disparoEnabled ? "Clique para desativar disparos automáticos" : "Clique para ativar disparos automáticos"}
            style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "8px 14px", borderRadius: 8, cursor: togglingDisparo ? "not-allowed" : "pointer",
              border: `1px solid ${disparoEnabled ? "var(--success)" : "var(--border)"}`,
              background: disparoEnabled ? "var(--success)15" : "var(--surface2)",
              color: disparoEnabled ? "var(--success)" : "var(--muted)",
              fontWeight: 600, fontSize: 12,
              transition: "all 0.2s", opacity: togglingDisparo ? 0.6 : 1,
              marginLeft: "auto",
            }}
          >
            {disparoEnabled ? <Bell size={13} /> : <BellOff size={13} />}
            <span>Disparo Auto</span>
            {/* track */}
            <span style={{
              display: "inline-flex", width: 34, height: 18, borderRadius: 9,
              background: disparoEnabled ? "var(--success)" : "var(--border)",
              alignItems: "center", padding: "0 2px",
              transition: "background 0.2s",
            }}>
              <span style={{
                width: 14, height: 14, borderRadius: "50%", background: "#fff",
                transform: disparoEnabled ? "translateX(16px)" : "translateX(0)",
                transition: "transform 0.2s",
              }} />
            </span>
          </button>

          {message && (
            <span style={{ fontSize: 12, color: message.type === "error" ? "var(--error)" : "var(--success)" }}>
              {message.text}
            </span>
          )}
        </div>

        {/* cards de stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, minmax(0, 1fr))", gap: 14, marginBottom: 16 }}>
          {([
            { label: "Candidatos", key: "candidate", icon: Repeat2, color: "var(--muted)" },
            { label: "IA Aprovados", key: "ai_approved", icon: CheckCircle2, color: "var(--accent)" },
            { label: "Revisão", key: "needs_review", icon: ShieldCheck, color: "var(--warn)" },
            { label: "Disparados", key: "dispatched", icon: Send, color: "var(--warn)" },
            { label: "Convertidos", key: "converted", icon: AlertTriangle, color: "var(--success)" },
          ] as const).map(({ label, key, icon: Icon, color }) => (
            <div
              key={label}
              onClick={() => { setActiveStatus(key); setPage(1); }}
              style={{
                background: "var(--surface)", border: `1px solid ${activeStatus === key ? color : "var(--border)"}`,
                borderRadius: 12, padding: "16px 20px", cursor: "pointer",
                transition: "border-color 0.15s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  {label}
                </span>
                <Icon size={15} color={color} />
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text)" }}>
                {stats?.[key] ?? 0}
              </div>
            </div>
          ))}
        </div>

        {/* card receita potencial */}
        {receitaPotencial > 0 && (
          <div style={{
            background: "linear-gradient(135deg, var(--accent)12, transparent)",
            border: "1px solid var(--accent)44",
            borderRadius: 12, padding: "14px 20px", marginBottom: 24,
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <DollarSign size={18} color="var(--accent)" />
            <div>
              <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                Receita Prevista — aprovados visíveis
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "var(--accent)" }}>
                {receitaPotencial.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 0 })}
              </div>
            </div>
            <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>
              em recompra prevista
            </span>
          </div>
        )}

        {/* tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, flexWrap: "wrap" }}>
          {STATUS_TABS.map(({ key, label }) => {
            const isActive = activeStatus === key;
            const count = key && stats ? (stats as Record<string, number>)[key] ?? 0 : null;
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
                {count !== null && (
                  <span style={{ marginLeft: 6, opacity: 0.75 }}>{count}</span>
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
              Central Operacional de Recorrência
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{data?.total ?? 0} registros</span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : !data || data.targets.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhum registro. Rode o script para gerar candidatos.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Cliente", "Status", "Janela", "Tier", "Confiança", "Pedido Sugerido", "Valor Médio", "Motivo IA"].map(h => (
                      <th key={h} style={{
                        padding: "10px 16px", textAlign: "left",
                        fontSize: 11, fontWeight: 700, color: "var(--muted)",
                        textTransform: "uppercase", letterSpacing: 0.5, whiteSpace: "nowrap",
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.targets.map(t => {
                    const ai = parseAi(t.ai_reasoning);
                    return (
                      <tr
                        key={t.id}
                        onClick={() => openDetail(t.id)}
                        style={{ borderTop: "1px solid var(--border)", cursor: "pointer" }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = "var(--surface2)"}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = "transparent"}
                      >
                        {/* Cliente */}
                        <td style={{ padding: "10px 16px", minWidth: 160 }}>
                          <div style={{ color: "var(--text)", fontWeight: 700, fontSize: 13 }}>
                            {t.customer_name || "—"}
                          </div>
                          <div style={{ color: "var(--muted)", fontSize: 11 }}>{t.cpf_cnpj}</div>
                        </td>

                        {/* Status */}
                        <td style={{ padding: "10px 16px" }}>
                          <StatusBadge status={t.status} />
                        </td>

                        {/* Janela — coluna mais importante, visualmente destacada */}
                        <td style={{ padding: "10px 16px" }}>
                          <JanelaBadge days={t.days_until_predicted ?? null} />
                        </td>

                        {/* Tier */}
                        <td style={{ padding: "10px 16px" }}>
                          <TierBadge tier={t.recurrence_tier} />
                        </td>

                        {/* Confiança */}
                        <td style={{ padding: "10px 16px" }}>
                          <ConfiancaBadge value={ai?.nivel_confianca} />
                        </td>

                        {/* Pedido Sugerido */}
                        <td style={{ padding: "10px 16px", maxWidth: 200 }}>
                          <span style={{
                            color: ai?.pedido_sugerido?.length ? "var(--text)" : "var(--muted)",
                            fontSize: 12,
                            display: "block", overflow: "hidden",
                            whiteSpace: "nowrap", textOverflow: "ellipsis",
                          }}>
                            {pedidoInline(ai)}
                          </span>
                        </td>

                        {/* Valor Médio */}
                        <td style={{ padding: "10px 16px", whiteSpace: "nowrap" }}>
                          <span style={{
                            color: ai?.valor_medio ? "var(--accent)" : "var(--muted)",
                            fontWeight: 700, fontSize: 13,
                          }}>
                            {fmtBRL(ai?.valor_medio)}
                          </span>
                        </td>

                        {/* Motivo IA */}
                        <td style={{ padding: "10px 16px", maxWidth: 220 }}>
                          <span style={{
                            color: "var(--muted)", fontSize: 11,
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          } as React.CSSProperties}>
                            {ai?.motivo || "—"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
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
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
      `}</style>
    </div>
  );
}
