"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Loader2,
  Plus,
  QrCode,
  RefreshCw,
  Server,
  Smartphone,
  Trash2,
  WifiOff,
  X,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { conexaoApi } from "@/lib/api";
import type {
  ConexaoStatus,
  CreateInstanceResult,
  EvolutionInstance,
  EvolutionInstancesResponse,
  QrCodeResult,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function stateColor(status: string) {
  const s = status.toLowerCase();
  if (s === "open" || s === "connected") return "var(--success)";
  if (s === "connecting" || s === "created") return "var(--warn)";
  return "var(--error)";
}

function stateLabel(status: string) {
  const s = status.toLowerCase();
  if (s === "open") return "Conectado";
  if (s === "connected") return "Conectado";
  if (s === "close" || s === "closed") return "Desconectado";
  if (s === "connecting") return "Conectando...";
  if (s === "created") return "Criado";
  return status;
}

// ---------------------------------------------------------------------------
// QR Code Modal
// ---------------------------------------------------------------------------

function QrModal({
  instance,
  onClose,
}: {
  instance: EvolutionInstance;
  onClose: () => void;
}) {
  const [qr, setQr] = useState<QrCodeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await conexaoApi.getQrCode(instance.instanceName);
      setQr(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao buscar QR code");
    } finally {
      setLoading(false);
    }
  }, [instance.instanceName]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 16,
          padding: 28,
          width: 340,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
          <span style={{ fontWeight: 700, fontSize: 15, color: "var(--text)" }}>
            QR Code — {instance.instanceName}
          </span>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
            <X size={18} />
          </button>
        </div>

        {loading && (
          <div style={{ padding: 48, color: "var(--muted)", display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <Loader2 size={32} style={{ animation: "spin 1s linear infinite" }} />
            <span style={{ fontSize: 13 }}>Carregando QR code...</span>
          </div>
        )}

        {error && (
          <div style={{ color: "var(--error)", fontSize: 13, textAlign: "center", padding: "12px 0" }}>
            {error}
          </div>
        )}

        {qr && !loading && (
          <>
            <img
              src={qr.base64}
              alt="QR Code WhatsApp"
              style={{ width: 260, height: 260, borderRadius: 8, border: "1px solid var(--border)" }}
            />
            <span style={{ fontSize: 11, color: "var(--muted)", textAlign: "center" }}>
              Abra o WhatsApp → Aparelhos conectados → Conectar um aparelho
            </span>
          </>
        )}

        <div style={{ display: "flex", gap: 8, width: "100%" }}>
          <button
            onClick={load}
            disabled={loading}
            style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              background: "var(--surface2)", border: "1px solid var(--border)",
              borderRadius: 8, padding: "8px 0",
              fontSize: 13, fontWeight: 600, color: "var(--text)",
              cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
          <button
            onClick={onClose}
            style={{
              flex: 1, background: "none", border: "1px solid var(--border)",
              borderRadius: 8, padding: "8px 0",
              fontSize: 13, fontWeight: 600, color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create Instance Modal
// ---------------------------------------------------------------------------

function CreateModal({
  onClose,
  onCreated,
  existingNames,
}: {
  onClose: () => void;
  onCreated: (result: CreateInstanceResult) => void;
  existingNames: string[];
}) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const nameTrimmed = name.trim();
  const isDuplicate = existingNames.some(
    (n) => n.toLowerCase() === nameTrimmed.toLowerCase()
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!nameTrimmed || isDuplicate) return;
    setLoading(true);
    setError(null);
    try {
      const result = await conexaoApi.createInstance({ name: nameTrimmed });
      onCreated(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar instancia");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 16,
          padding: 28,
          width: 380,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 700, fontSize: 16, color: "var(--text)" }}>Nova Instância</span>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Nome da Instância *
            </label>
            <input
              ref={inputRef}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ex: spres-principal"
              required
              style={{
                background: "var(--surface2)",
                border: `1px solid ${isDuplicate ? "var(--error)" : "var(--border)"}`,
                borderRadius: 8, padding: "10px 12px",
                fontSize: 13, color: "var(--text)", outline: "none",
                transition: "border-color 0.15s",
              }}
            />
            {isDuplicate && (
              <span style={{ fontSize: 12, color: "var(--error)", display: "flex", alignItems: "center", gap: 5 }}>
                <AlertTriangle size={12} />
                Já existe uma instância com este nome. Escolha outro.
              </span>
            )}
          </div>

          {/* Info: configurações automáticas */}
          <div
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "10px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Configurado automaticamente
            </span>
            {[
              ["Webhook", "Gerado pelo sistema"],
              ["Ligações", "Recusadas — \"No momento não consigo atender. Envie uma mensagem!\""],
              ["Eventos", "message_upsert + conexão ativados"],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", gap: 6, fontSize: 12 }}>
                <span style={{ color: "var(--muted)", minWidth: 60 }}>{k}:</span>
                <span style={{ color: "var(--text)" }}>{v}</span>
              </div>
            ))}
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8, padding: "10px 14px",
              fontSize: 12, color: "var(--error)",
            }}>
              {error}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button
              type="submit"
              disabled={loading || !nameTrimmed || isDuplicate}
              style={{
                flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: "var(--accent)", color: "#fff", border: "none",
                borderRadius: 8, padding: "10px 0",
                fontSize: 14, fontWeight: 700,
                cursor: (loading || !nameTrimmed || isDuplicate) ? "not-allowed" : "pointer",
                opacity: (loading || !nameTrimmed || isDuplicate) ? 0.6 : 1,
              }}
            >
              {loading ? <Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} /> : <QrCode size={15} />}
              {loading ? "Criando..." : "Criar e ver QR Code"}
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "10px 20px", background: "none",
                border: "1px solid var(--border)", borderRadius: 8,
                fontSize: 14, color: "var(--muted)", cursor: "pointer",
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Instance Card
// ---------------------------------------------------------------------------

function AgentToggle({
  enabled,
  loading,
  onClick,
}: {
  enabled: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      title={enabled ? "Agente ativo — clique para desligar" : "Agente desligado — clique para ligar"}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "5px 12px",
        borderRadius: 7,
        fontSize: 12,
        fontWeight: 600,
        cursor: loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.6 : 1,
        border: enabled ? "1px solid var(--success)" : "1px solid var(--muted)",
        background: enabled ? "rgba(34,197,94,0.10)" : "var(--surface2)",
        color: enabled ? "var(--success)" : "var(--muted)",
        transition: "all 0.15s",
      }}
    >
      <Bot size={13} />
      {loading ? "..." : enabled ? "Agente ON" : "Agente OFF"}
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: enabled ? "var(--success)" : "var(--muted)",
          display: "inline-block",
          marginLeft: 2,
        }}
      />
    </button>
  );
}

function InstanceCard({
  instance,
  onQrCode,
  onRestart,
  onDisconnect,
  onDelete,
  onAgentToggle,
  agentEnabled,
  agentLoading,
  busy,
}: {
  instance: EvolutionInstance;
  onQrCode: () => void;
  onRestart: () => void;
  onDisconnect: () => void;
  onDelete: () => void;
  onAgentToggle: () => void;
  agentEnabled: boolean;
  agentLoading: boolean;
  busy: boolean;
}) {
  const isConnected = ["open", "connected"].includes(instance.status.toLowerCase());
  const color = stateColor(instance.status);

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 36, height: 36,
            borderRadius: "50%",
            background: "var(--surface2)",
            border: `2px solid ${color}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Smartphone size={16} color={color} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {instance.instanceName}
          </div>
          {instance.phoneNumber && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>{instance.phoneNumber}</div>
          )}
        </div>
        <span
          style={{
            fontSize: 11, fontWeight: 700,
            color, background: `${color}18`,
            border: `1px solid ${color}40`,
            borderRadius: 6, padding: "3px 8px",
            whiteSpace: "nowrap",
          }}
        >
          {stateLabel(instance.status)}
        </span>
      </div>

      {isConnected && (
        <div
          style={{
            padding: "10px 18px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: agentEnabled ? "rgba(34,197,94,0.04)" : "var(--surface2)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
              Agente Marcela
            </span>
            <span style={{ fontSize: 11, color: agentEnabled ? "var(--success)" : "var(--muted)" }}>
              {agentEnabled ? "Respondendo automaticamente" : "Silenciada"}
            </span>
          </div>
          <AgentToggle
            enabled={agentEnabled}
            loading={agentLoading}
            onClick={onAgentToggle}
          />
        </div>
      )}

      <div style={{ padding: "12px 18px", display: "flex", flexWrap: "wrap", gap: 8 }}>
        {!isConnected && (
          <ActionBtn
            icon={<QrCode size={13} />}
            label="QR Code"
            onClick={onQrCode}
            disabled={busy}
            variant="primary"
          />
        )}
        <ActionBtn
          icon={<RefreshCw size={13} />}
          label="Reiniciar"
          onClick={onRestart}
          disabled={busy}
          variant="secondary"
        />
        {isConnected && (
          <ActionBtn
            icon={<WifiOff size={13} />}
            label="Desconectar"
            onClick={onDisconnect}
            disabled={busy}
            variant="warn"
          />
        )}
        <ActionBtn
          icon={<Trash2 size={13} />}
          label="Apagar"
          onClick={onDelete}
          disabled={busy}
          variant="danger"
        />
      </div>
    </div>
  );
}

function ActionBtn({
  icon, label, onClick, disabled, variant,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled: boolean;
  variant: "primary" | "secondary" | "warn" | "danger";
}) {
  const colors: Record<string, [string, string]> = {
    primary: ["var(--accent)", "var(--accent)"],
    secondary: ["var(--surface2)", "var(--text)"],
    warn: ["rgba(245,158,11,0.12)", "var(--warn)"],
    danger: ["rgba(239,68,68,0.1)", "var(--error)"],
  };
  const [bg, fg] = colors[variant];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex", alignItems: "center", gap: 5,
        background: variant === "primary" ? bg : bg,
        color: variant === "primary" ? "#fff" : fg,
        border: variant === "primary" ? "none" : `1px solid ${fg}30`,
        borderRadius: 7, padding: "6px 12px",
        fontSize: 12, fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {icon}
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

function Toast({ msg, type, onClose }: { msg: string; type: "success" | "error"; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      style={{
        position: "fixed", bottom: 24, right: 24, zIndex: 2000,
        background: type === "success" ? "var(--success)" : "var(--error)",
        color: "#fff", borderRadius: 10, padding: "12px 20px",
        fontSize: 13, fontWeight: 600,
        display: "flex", alignItems: "center", gap: 10,
        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
      }}
    >
      {type === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      {msg}
      <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#fff", marginLeft: 4 }}>
        <X size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ConexaoPage() {
  const [apiStatus, setApiStatus] = useState<ConexaoStatus | null>(null);
  const [data, setData] = useState<EvolutionInstancesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [qrInstance, setQrInstance] = useState<EvolutionInstance | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [busyMap, setBusyMap] = useState<Record<string, boolean>>({});
  const [agentMap, setAgentMap] = useState<Record<string, boolean>>({});
  const [agentLoadingMap, setAgentLoadingMap] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const showToast = (msg: string, type: "success" | "error" = "success") =>
    setToast({ msg, type });

  const setBusy = (name: string, val: boolean) =>
    setBusyMap((p) => ({ ...p, [name]: val }));

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, instances] = await Promise.all([
        conexaoApi.status(),
        conexaoApi.listInstances().catch(() => null),
      ]);
      setApiStatus(status);
      if (instances) {
        setData(instances);
        const connected = (instances.instances ?? []).filter(
          (i) => ["open", "connected"].includes(i.status.toLowerCase())
        );
        const agentStatuses = await Promise.all(
          connected.map((i) =>
            conexaoApi.getAgentStatus(i.instanceName).catch(() => ({ instanceName: i.instanceName, agent_enabled: true }))
          )
        );
        setAgentMap(
          Object.fromEntries(agentStatuses.map((s) => [s.instanceName, s.agent_enabled]))
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleDelete(name: string) {
    if (!confirm(`Apagar a instância "${name}"? Esta ação não pode ser desfeita.`)) return;
    setBusy(name, true);
    try {
      await conexaoApi.deleteInstance(name);
      showToast(`Instância "${name}" apagada`);
      loadAll();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Erro ao apagar", "error");
    } finally {
      setBusy(name, false);
    }
  }

  async function handleDisconnect(name: string) {
    setBusy(name, true);
    try {
      await conexaoApi.disconnectInstance(name);
      showToast(`"${name}" desconectada`);
      loadAll();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Erro ao desconectar", "error");
    } finally {
      setBusy(name, false);
    }
  }

  async function handleRestart(name: string) {
    setBusy(name, true);
    try {
      await conexaoApi.restartInstance(name);
      showToast(`"${name}" reiniciada`);
      setTimeout(loadAll, 2000);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Erro ao reiniciar", "error");
    } finally {
      setBusy(name, false);
    }
  }

  async function handleAgentToggle(name: string) {
    const current = agentMap[name] ?? true;
    const next = !current;
    setAgentLoadingMap((p) => ({ ...p, [name]: true }));
    try {
      const result = await conexaoApi.toggleAgent(name, next);
      setAgentMap((p) => ({ ...p, [name]: result.agent_enabled }));
      showToast(`Agente ${result.agent_enabled ? "ligado" : "desligado"} para "${name}"`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Erro ao atualizar agente", "error");
    } finally {
      setAgentLoadingMap((p) => ({ ...p, [name]: false }));
    }
  }

  function handleCreated(result: CreateInstanceResult) {
    setShowCreate(false);
    showToast(`Instância "${result.instanceName}" criada`);
    loadAll();
    // Sempre abre o QR modal para conectar o WhatsApp
    const inst: EvolutionInstance = {
      instanceName: result.instanceName,
      instanceId: result.instanceId,
      status: result.status,
    };
    setQrInstance(inst);
  }

  const instances = data?.instances ?? [];
  const apiOnline = apiStatus?.api_online ?? data?.api_online ?? false;
  const apiUrl = apiStatus?.api_url ?? data?.api_url ?? null;
  const envOk = apiStatus?.env ?? data?.env ?? {};

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Conexao — Evolution API" />

      <div style={{ flex: 1, overflow: "auto", padding: 28 }}>

        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
          <button
            onClick={loadAll}
            disabled={loading}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--accent)", color: "#fff", border: "none",
              borderRadius: 8, padding: "8px 18px",
              fontWeight: 600, fontSize: 13,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            <RefreshCw size={14} style={{ animation: loading ? "spin 1s linear infinite" : undefined }} />
            {loading ? "Carregando..." : "Atualizar"}
          </button>

          <button
            onClick={() => setShowCreate(true)}
            disabled={!apiOnline}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              background: "var(--surface)", color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 8, padding: "8px 18px",
              fontWeight: 600, fontSize: 13,
              cursor: !apiOnline ? "not-allowed" : "pointer",
              opacity: !apiOnline ? 0.5 : 1,
            }}
          >
            <Plus size={14} />
            Nova Instância
          </button>

          {error && <span style={{ fontSize: 12, color: "var(--error)" }}>{error}</span>}
        </div>

        {/* API status cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 14, marginBottom: 24 }}>
          {[
            {
              label: "API",
              value: loading ? "..." : apiOnline ? "Online" : "Offline",
              icon: Server,
              color: apiOnline ? "var(--success)" : "var(--error)",
            },
            {
              label: "URL",
              value: apiUrl || "Não configurada",
              icon: Server,
              color: apiUrl ? "var(--accent)" : "var(--warn)",
            },
            {
              label: "Instâncias",
              value: loading ? "..." : String(instances.length),
              icon: Smartphone,
              color: "var(--accent)",
            },
            {
              label: "Conectadas",
              value: loading ? "..." : String(instances.filter((i) => ["open", "connected"].includes(i.status.toLowerCase())).length),
              icon: CheckCircle2,
              color: "var(--success)",
            },
          ].map(({ label, value, icon: Icon, color }) => (
            <div
              key={label}
              style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 12, padding: "14px 18px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>{label}</span>
                <Icon size={15} color={color} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        {/* Main content: instances + env vars */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20, alignItems: "start" }}>

          {/* Instances grid */}
          <div>
            <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 13, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                Instâncias ({instances.length})
              </span>
            </div>

            {!loading && instances.length === 0 && (
              <div
                style={{
                  background: "var(--surface)", border: "1px dashed var(--border)",
                  borderRadius: 14, padding: "40px 24px",
                  textAlign: "center", color: "var(--muted)", fontSize: 13,
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
                }}
              >
                <Smartphone size={28} color="var(--muted)" />
                <div>
                  {apiOnline
                    ? "Nenhuma instância criada. Clique em \"Nova Instância\" para começar."
                    : "Configure as variáveis da Evolution API para gerenciar instâncias."}
                </div>
              </div>
            )}

            {loading && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)", padding: "20px 0" }}>
                <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} />
                <span style={{ fontSize: 13 }}>Carregando instâncias...</span>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
              {instances.map((inst) => (
                <InstanceCard
                  key={inst.instanceName}
                  instance={inst}
                  busy={busyMap[inst.instanceName] ?? false}
                  agentEnabled={agentMap[inst.instanceName] ?? true}
                  agentLoading={agentLoadingMap[inst.instanceName] ?? false}
                  onQrCode={() => setQrInstance(inst)}
                  onRestart={() => handleRestart(inst.instanceName)}
                  onDisconnect={() => handleDisconnect(inst.instanceName)}
                  onDelete={() => handleDelete(inst.instanceName)}
                  onAgentToggle={() => handleAgentToggle(inst.instanceName)}
                />
              ))}
            </div>
          </div>

          {/* Right panel: env vars + API details */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <section
              style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 14, overflow: "hidden",
              }}
            >
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  Variáveis de Ambiente
                </span>
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                {Object.entries(envOk).map(([key, ok]) => (
                  <div
                    key={key}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      background: "var(--surface2)", borderRadius: 8,
                      padding: "8px 10px", border: "1px solid var(--border)",
                    }}
                  >
                    <span style={{ fontSize: 11, color: "var(--text)", fontFamily: "monospace" }}>{key}</span>
                    <span style={{ fontSize: 11, color: ok ? "var(--success)" : "var(--error)", fontWeight: 700 }}>
                      {ok ? "OK" : "FALTANDO"}
                    </span>
                  </div>
                ))}
                {Object.keys(envOk).length === 0 && (
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>Carregando...</span>
                )}
              </div>
            </section>

            <section
              style={{
                background: "var(--surface)", border: "1px solid var(--border)",
                borderRadius: 14, overflow: "hidden",
              }}
            >
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 700, fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                  Config Padrão ao Criar
                </span>
              </div>
              <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  ["Recusar Ligações", "Sempre ativo"],
                  ["Message Upsert", "Ativo via webhook"],
                  ["Base64", "Ativo via webhook"],
                  ["Integração", "WHATSAPP-BAILEYS"],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>{k}</span>
                    <span style={{ fontSize: 12, color: "var(--text)", fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>

        </div>
      </div>

      {qrInstance && (
        <QrModal instance={qrInstance} onClose={() => setQrInstance(null)} />
      )}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
          existingNames={instances.map((i) => i.instanceName)}
        />
      )}
      {toast && (
        <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
