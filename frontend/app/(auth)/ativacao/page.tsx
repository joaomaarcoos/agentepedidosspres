"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bell, BellOff, Bot, CheckCircle2, ChevronLeft, ChevronRight,
  MessageSquare, Play, RefreshCw, Send, Target, X, XCircle, Zap,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { ativacaoApi, settingsApi } from "@/lib/api";
import type { AtivacaoOverview, AtivacaoAiData, RecorrenciaTarget } from "@/lib/types";

// ─── AI data parser ───────────────────────────────────────────────────────────

function parseAi(raw: string | null): AtivacaoAiData | null {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

// ─── Constantes visuais ───────────────────────────────────────────────────────

const TIPO_LABEL: Record<string, string> = {
  cliente_irregular: "Irregular",
  cliente_adormecido: "Adormecido",
  cliente_novo_potencial: "Potencial",
  descartar: "Descartar",
};

const TIPO_COLOR: Record<string, string> = {
  cliente_irregular: "var(--warn)",
  cliente_adormecido: "var(--muted)",
  cliente_novo_potencial: "var(--accent)",
  descartar: "var(--error)",
};

const CONFIANCA_COLOR: Record<string, string> = {
  alto: "var(--success)", medio: "var(--warn)", baixo: "var(--error)",
};

const CONFIANCA_LABEL: Record<string, string> = {
  alto: "Alta", medio: "Média", baixo: "Baixa",
};

const STATUS_LABEL: Record<string, string> = {
  activation_candidate: "Candidato",
  activation_approved: "IA Aprovado",
  activation_rejected: "IA Rejeitado",
  dispatched: "Disparado",
};

const STATUS_COLOR: Record<string, string> = {
  activation_candidate: "var(--muted)",
  activation_approved: "var(--accent)",
  activation_rejected: "var(--error)",
  dispatched: "var(--warn)",
};

const STATUS_TABS = [
  { key: "", label: "Todos" },
  { key: "activation_candidate", label: "Candidatos" },
  { key: "activation_approved", label: "IA Aprovados" },
  { key: "activation_rejected", label: "Rejeitados" },
  { key: "dispatched", label: "Disparados" },
];

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("pt-BR");
}

// ─── Badge helpers ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
      background: `${STATUS_COLOR[status] ?? "var(--muted)"}22`,
      color: STATUS_COLOR[status] ?? "var(--muted)",
      border: `1px solid ${STATUS_COLOR[status] ?? "var(--muted)"}44`,
    }}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function TipoBadge({ tipo }: { tipo: string | undefined }) {
  if (!tipo) return <span style={{ color: "var(--muted)" }}>—</span>;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
      background: `${TIPO_COLOR[tipo] ?? "var(--muted)"}22`,
      color: TIPO_COLOR[tipo] ?? "var(--muted)",
      border: `1px solid ${TIPO_COLOR[tipo] ?? "var(--muted)"}44`,
    }}>
      {TIPO_LABEL[tipo] ?? tipo}
    </span>
  );
}

// ─── Detail Drawer ────────────────────────────────────────────────────────────

function DetailDrawer({
  target,
  onClose,
}: {
  target: RecorrenciaTarget;
  onClose: () => void;
}) {
  const ai = parseAi(target.ai_reasoning);

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
          zIndex: 40, backdropFilter: "blur(2px)",
        }}
      />
      <div style={{
        position: "fixed", right: 0, top: 0, bottom: 0, width: 680,
        background: "var(--bg)", borderLeft: "1px solid var(--border)",
        zIndex: 50, overflowY: "auto", padding: 32,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text)", marginBottom: 6 }}>
              {target.customer_name || target.cpf_cnpj}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <StatusBadge status={target.status} />
              {ai?.tipo_abordagem && <TipoBadge tipo={ai.tipo_abordagem} />}
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
            <X size={20} />
          </button>
        </div>

        {/* Dados do cliente */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 24 }}>
          {[
            { label: "CPF/CNPJ", value: target.cpf_cnpj },
            { label: "Telefone", value: target.customer_phone || "—" },
            { label: "Último Pedido", value: fmtDate(target.last_order_date) },
            { label: "Pedidos 30d", value: target.orders_count_30d ?? "—" },
            { label: "Candidato desde", value: fmtDate(target.created_at) },
            { label: "Atualizado", value: fmtDate(target.updated_at) },
          ].map(({ label, value }) => (
            <div key={label} style={{
              background: "var(--surface)", border: "1px solid var(--border)",
              borderRadius: 10, padding: "12px 14px",
            }}>
              <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 4 }}>
                {label}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)" }}>
                {String(value)}
              </div>
            </div>
          ))}
        </div>

        {/* Decisão da IA */}
        {ai && (
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: 20, marginBottom: 20,
          }}>
            <div style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 14 }}>
              Decisão da IA
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                {ai.decisao === "sim"
                  ? <CheckCircle2 size={16} color="var(--success)" />
                  : <XCircle size={16} color="var(--error)" />}
                <span style={{ fontSize: 13, fontWeight: 600, color: ai.decisao === "sim" ? "var(--success)" : "var(--error)" }}>
                  {ai.decisao === "sim" ? "Abordar" : "Descartar"}
                </span>
              </div>
              {ai.nivel_confianca && (
                <span style={{ fontSize: 12, color: CONFIANCA_COLOR[ai.nivel_confianca] ?? "var(--muted)" }}>
                  Confiança: {CONFIANCA_LABEL[ai.nivel_confianca] ?? ai.nivel_confianca}
                </span>
              )}
              {ai.tipo_abordagem && <TipoBadge tipo={ai.tipo_abordagem} />}
            </div>
            {ai.motivo && (
              <p style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.5, margin: 0 }}>
                {ai.motivo}
              </p>
            )}
          </div>
        )}

        {/* Mensagem sugerida */}
        {ai?.mensagem && (
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: 20, marginBottom: 20,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <MessageSquare size={14} color="var(--accent)" />
              <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                Mensagem Sugerida
              </span>
            </div>
            <pre style={{
              margin: 0, fontSize: 13, color: "var(--text)", whiteSpace: "pre-wrap",
              fontFamily: "inherit", lineHeight: 1.6,
              background: "var(--surface2)", borderRadius: 8, padding: 14,
            }}>
              {ai.mensagem}
            </pre>
          </div>
        )}

        {/* Top produtos */}
        {(target.top_items_json?.length ?? 0) > 0 && (
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: 20, marginBottom: 20,
          }}>
            <div style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              Produtos do Histórico
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ color: "var(--muted)" }}>
                  {["Produto", "Aparições", "Qtd Total"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "4px 8px", fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {target.top_items_json!.map((item, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "6px 8px", color: "var(--text)" }}>
                      {item.desPro} <span style={{ color: "var(--muted)", fontSize: 10 }}>[{item.codPro}]</span>
                    </td>
                    <td style={{ padding: "6px 8px", color: "var(--muted)" }}>{item.aparicoes}x</td>
                    <td style={{ padding: "6px 8px", color: "var(--muted)" }}>{item.total_qtd}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Últimos 3 pedidos */}
        {(target.last_3_orders_json?.length ?? 0) > 0 && (
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: 20,
          }}>
            <div style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              Últimos 3 Pedidos
            </div>
            {target.last_3_orders_json!.map((p, i) => (
              <div key={i} style={{
                borderTop: i > 0 ? "1px solid var(--border)" : undefined,
                paddingTop: i > 0 ? 12 : 0, paddingBottom: 12,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                    Pedido {p.numero || `#${i + 1}`} — {p.data}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>
                    R$ {p.valor_total.toFixed(2)}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.6 }}>
                  {(p.itens || []).map((it, j) => (
                    <span key={j}>
                      {it.desPro} ×{it.qtdPed}
                      {j < (p.itens?.length ?? 0) - 1 ? " · " : ""}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function AtivacaoPage() {
  const [activeStatus, setActiveStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AtivacaoOverview | null>(null);
  const [selected, setSelected] = useState<RecorrenciaTarget | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [validating, setValidating] = useState(false);
  const [pipelining, setPipelining] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "error" | "success" } | null>(null);
  const [disparoEnabled, setDisparoEnabled] = useState(true);
  const [togglingDisparo, setTogglingDisparo] = useState(false);

  const load = useCallback(async (targetPage = 1, status = activeStatus) => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await ativacaoApi.list({ status: status || undefined, page: targetPage });
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
      .then(s => setDisparoEnabled(s.disparo_ativacao))
      .catch(() => {});
  }, []);

  const handleToggleDisparo = async () => {
    setTogglingDisparo(true);
    try {
      await settingsApi.setDisparo("disparo_ativacao_enabled", !disparoEnabled);
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
      const result = await ativacaoApi.runScript();
      setMessage({
        text: `Geração: ${result.eligible} elegíveis, ${result.inserted} inseridos, ${result.skipped_cooldown} em cooldown`,
        type: result.errors.length > 0 ? "error" : "success",
      });
      await load(1, activeStatus);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao gerar candidatos", type: "error" });
    } finally {
      setRunning(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setMessage(null);
    try {
      const result = await ativacaoApi.validate({ limit: 20 });
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

  const handlePipeline = async () => {
    setPipelining(true);
    setMessage(null);
    try {
      const result = await ativacaoApi.pipeline("manual");
      setMessage({
        text: `Pipeline: ${result.script.eligible} elegíveis, ${result.validate.approved} aprovados pela IA`,
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
      const detail = await ativacaoApi.detail(id);
      setSelected(detail);
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : "Falha ao abrir detalhe", type: "error" });
    }
  };

  const stats = data?.stats;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Ativação Comercial" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>

        {/* ações */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24, flexWrap: "wrap" }}>
          <button
            onClick={handleRunScript}
            disabled={running || loading || pipelining}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--surface2)", color: "var(--text)",
              border: "1px solid var(--border)", borderRadius: 8,
              padding: "8px 16px", fontWeight: 600, fontSize: 13,
              cursor: running ? "not-allowed" : "pointer", opacity: running ? 0.7 : 1,
            }}
          >
            <Play size={13} style={{ animation: running ? "spin 1s linear infinite" : undefined }} />
            {running ? "Gerando..." : "Gerar Candidatos"}
          </button>

          <button
            onClick={handleValidate}
            disabled={validating || loading || pipelining}
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
            onClick={handlePipeline}
            disabled={pipelining || running || validating}
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
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14, marginBottom: 16 }}>
          {([
            { label: "Candidatos", key: "activation_candidate", icon: Target, color: "var(--muted)" },
            { label: "IA Aprovados", key: "activation_approved", icon: CheckCircle2, color: "var(--accent)" },
            { label: "IA Rejeitados", key: "activation_rejected", icon: XCircle, color: "var(--error)" },
            { label: "Disparados", key: "dispatched", icon: Send, color: "var(--warn)" },
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

        {/* tabs de status */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid var(--border)", paddingBottom: 0 }}>
          {STATUS_TABS.map(({ key, label }) => {
            const count = key ? (stats?.[key as keyof typeof stats] ?? 0) : (data?.total ?? 0);
            const isActive = activeStatus === key;
            return (
              <button
                key={key}
                onClick={() => { setActiveStatus(key); setPage(1); }}
                style={{
                  padding: "8px 14px", fontSize: 12, fontWeight: isActive ? 700 : 400,
                  color: isActive ? "var(--accent)" : "var(--muted)",
                  background: "none", border: "none",
                  borderBottom: isActive ? "2px solid var(--accent)" : "2px solid transparent",
                  cursor: "pointer", transition: "all 0.15s",
                }}
              >
                {label}
                {count > 0 && (
                  <span style={{
                    marginLeft: 6, fontSize: 10, fontWeight: 700,
                    background: isActive ? "var(--accent)" : "var(--surface2)",
                    color: isActive ? "#fff" : "var(--muted)",
                    padding: "1px 6px", borderRadius: 10,
                  }}>
                    {count}
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
              Central Operacional de Ativação
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{data?.total ?? 0} registros</span>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Carregando...</div>
          ) : !data || data.targets.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
              Nenhum candidato. Execute "Gerar Candidatos" para criar registros a partir dos clientes rejeitados pela recorrência.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "var(--surface2)" }}>
                    {["Cliente", "Status", "Tipo Abordagem", "Confiança", "Motivo IA", "Mensagem Sugerida", "Último Contato"].map(h => (
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
                  {data.targets.map((t) => {
                    const ai = parseAi(t.ai_reasoning);
                    return (
                      <tr
                        key={t.id}
                        onClick={() => openDetail(t.id)}
                        style={{
                          borderTop: "1px solid var(--border)", cursor: "pointer",
                          transition: "background 0.1s",
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = "var(--surface2)")}
                        onMouseLeave={e => (e.currentTarget.style.background = "")}
                      >
                        <td style={{ padding: "12px 16px" }}>
                          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>
                            {t.customer_name || "—"}
                          </div>
                          <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.cpf_cnpj}</div>
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <StatusBadge status={t.status} />
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <TipoBadge tipo={ai?.tipo_abordagem} />
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          {ai?.nivel_confianca ? (
                            <span style={{ fontSize: 12, color: CONFIANCA_COLOR[ai.nivel_confianca] ?? "var(--muted)" }}>
                              {CONFIANCA_LABEL[ai.nivel_confianca] ?? ai.nivel_confianca}
                            </span>
                          ) : <span style={{ color: "var(--muted)" }}>—</span>}
                        </td>
                        <td style={{ padding: "12px 16px", maxWidth: 200 }}>
                          <div style={{
                            fontSize: 12, color: "var(--muted)",
                            overflow: "hidden", display: "-webkit-box",
                            WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                          }}>
                            {ai?.motivo || "—"}
                          </div>
                        </td>
                        <td style={{ padding: "12px 16px", maxWidth: 220 }}>
                          <div style={{
                            fontSize: 12, color: "var(--text)",
                            overflow: "hidden", display: "-webkit-box",
                            WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                          }}>
                            {ai?.mensagem || <span style={{ color: "var(--muted)" }}>—</span>}
                          </div>
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>
                            {t.last_contact_at ? fmtDate(t.last_contact_at) : "—"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* paginação */}
          {data && data.pages > 1 && (
            <div style={{
              padding: "12px 20px", borderTop: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Página {page} de {data.pages}
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => { const p = Math.max(1, page - 1); setPage(p); load(p); }}
                  disabled={page <= 1}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "6px 12px", borderRadius: 6, fontSize: 12,
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    cursor: page <= 1 ? "not-allowed" : "pointer", opacity: page <= 1 ? 0.5 : 1,
                    color: "var(--text)",
                  }}
                >
                  <ChevronLeft size={14} /> Anterior
                </button>
                <button
                  onClick={() => { const p = Math.min(data.pages, page + 1); setPage(p); load(p); }}
                  disabled={page >= data.pages}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    padding: "6px 12px", borderRadius: 6, fontSize: 12,
                    background: "var(--surface2)", border: "1px solid var(--border)",
                    cursor: page >= data.pages ? "not-allowed" : "pointer", opacity: page >= data.pages ? 0.5 : 1,
                    color: "var(--text)",
                  }}
                >
                  Próxima <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selected && <DetailDrawer target={selected} onClose={() => setSelected(null)} />}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
