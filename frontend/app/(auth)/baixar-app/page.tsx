"use client";

import { useEffect, useState } from "react";
import { Download, MonitorSmartphone, Share2, Smartphone } from "lucide-react";
import Header from "@/components/layout/Header";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

function isStandalone() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function getDevice() {
  const ua = window.navigator.userAgent;
  const isIos = /iPad|iPhone|iPod/.test(ua) || (ua.includes("Mac") && "ontouchend" in document);
  const isAndroid = /Android/i.test(ua);
  return { isIos, isAndroid };
}

export default function BaixarAppPage() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [status, setStatus] = useState("");
  const [standalone, setStandalone] = useState(false);
  const [device, setDevice] = useState({ isIos: false, isAndroid: false });

  useEffect(() => {
    setStandalone(isStandalone());
    setDevice(getDevice());

    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
      setStatus("");
    };

    const handleInstalled = () => {
      setStandalone(true);
      setStatus("Aplicativo instalado com sucesso.");
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleInstalled);

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleInstalled);
    };
  }, []);

  async function handleInstall() {
    if (standalone) {
      setStatus("O aplicativo ja esta instalado neste aparelho.");
      return;
    }

    if (device.isIos) {
      setStatus('No iPhone, toque em Compartilhar e depois em "Adicionar a Tela de Inicio".');
      return;
    }

    if (!installEvent) {
      setStatus('Se a janela nativa nao aparecer, abra o menu do Chrome e toque em "Instalar app" ou "Adicionar a tela inicial".');
      return;
    }

    await installEvent.prompt();
    const choice = await installEvent.userChoice;
    setInstallEvent(null);
    setStatus(choice.outcome === "accepted" ? "Instalacao iniciada." : "Instalacao cancelada.");
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header title="Baixar APP" />
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ maxWidth: 840 }}>
          <section
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              padding: 22,
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 18 }}>
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "var(--accent-glow)",
                  color: "var(--accent)",
                  flexShrink: 0,
                }}
              >
                <MonitorSmartphone size={21} />
              </div>
              <div>
                <h2 style={{ margin: "0 0 5px", fontSize: 18, color: "var(--text)" }}>
                  Instalar aplicativo
                </h2>
                <p style={{ margin: 0, maxWidth: 620, fontSize: 13, lineHeight: 1.5, color: "var(--muted)" }}>
                  Use o AgentePedidos como um app no celular. Ele abre em tela cheia, fica na tela inicial e ocupa menos espaco que o navegador.
                </p>
              </div>
            </div>

            <button
              onClick={handleInstall}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                minHeight: 44,
                padding: "0 18px",
                border: "none",
                borderRadius: 8,
                background: "var(--accent)",
                color: "#fff",
                fontSize: 13,
                fontWeight: 800,
                cursor: "pointer",
                boxShadow: "0 0 12px var(--accent-glow)",
              }}
            >
              <Download size={16} />
              {standalone ? "App instalado" : "Instalar aplicativo"}
            </button>

            {status && (
              <div
                style={{
                  marginTop: 14,
                  padding: "10px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--surface2)",
                  color: "var(--muted)",
                  fontSize: 12,
                  lineHeight: 1.45,
                }}
              >
                {status}
              </div>
            )}

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
                gap: 10,
                marginTop: 18,
              }}
            >
              <div style={{ border: "1px solid var(--border)", background: "var(--surface2)", borderRadius: 10, padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, fontWeight: 700, fontSize: 13 }}>
                  <Smartphone size={15} color="var(--accent)" />
                  Android (Chrome)
                </div>
                <ol style={{ margin: 0, paddingLeft: 18, color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>
                  <li>Toque em "Instalar aplicativo".</li>
                  <li>Confirme a instalacao no Chrome.</li>
                  <li>Se nao aparecer, abra o menu do Chrome e toque em "Instalar app".</li>
                </ol>
              </div>

              <div style={{ border: "1px solid var(--border)", background: "var(--surface2)", borderRadius: 10, padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, fontWeight: 700, fontSize: 13 }}>
                  <Share2 size={15} color="var(--accent)" />
                  iPhone (Safari)
                </div>
                <ol style={{ margin: 0, paddingLeft: 18, color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>
                  <li>Toque no botao Compartilhar.</li>
                  <li>Toque em "Adicionar a Tela de Inicio".</li>
                  <li>Confirme.</li>
                </ol>
              </div>
            </div>

            <p style={{ margin: "14px 0 0", color: "var(--muted)", fontSize: 12 }}>
              Para instalacao automatica no Android, acesse o sistema por HTTPS no Chrome.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
