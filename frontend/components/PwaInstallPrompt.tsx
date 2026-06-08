"use client";

import { Download, Share, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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

export default function PwaInstallPrompt() {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showIosHelp, setShowIosHelp] = useState(false);
  const [visible, setVisible] = useState(false);

  const device = useMemo(() => {
    if (typeof window === "undefined") return { isIos: false, isMobile: false };
    const ua = window.navigator.userAgent;
    const isIos = /iPad|iPhone|iPod/.test(ua) || (ua.includes("Mac") && "ontouchend" in document);
    const isMobile = isIos || /Android/i.test(ua);
    return { isIos, isMobile };
  }, []);

  useEffect(() => {
    if (!device.isMobile || isStandalone() || window.localStorage.getItem("pwa-install-dismissed") === "1") {
      return;
    }

    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);

    if (device.isIos) {
      const timer = window.setTimeout(() => setVisible(true), 1200);
      return () => {
        window.clearTimeout(timer);
        window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      };
    }

    return () => window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
  }, [device.isIos, device.isMobile]);

  async function handleInstall() {
    if (device.isIos) {
      setShowIosHelp(true);
      return;
    }

    if (!installEvent) {
      return;
    }

    await installEvent.prompt();
    const choice = await installEvent.userChoice;
    if (choice.outcome === "accepted") {
      setVisible(false);
    }
    setInstallEvent(null);
  }

  function dismiss() {
    window.localStorage.setItem("pwa-install-dismissed", "1");
    setVisible(false);
    setShowIosHelp(false);
  }

  if (!visible) return null;

  return (
    <div className="pwa-install-prompt" role="dialog" aria-label="Instalar aplicativo">
      <button className="pwa-install-close" onClick={dismiss} aria-label="Fechar aviso de instalacao">
        <X size={15} />
      </button>
      <div className="pwa-install-copy">
        <strong>AgentePedidos no celular</strong>
        <span>{device.isIos ? "Adicione o app a tela inicial." : "Instale para abrir mais rapido."}</span>
      </div>
      <button className="pwa-install-action" onClick={handleInstall}>
        {device.isIos ? <Share size={16} /> : <Download size={16} />}
        {device.isIos ? "Como adicionar" : "Instalar app"}
      </button>

      {showIosHelp && (
        <div className="pwa-ios-help">
          Toque em compartilhar no Safari e escolha "Adicionar a Tela de Inicio".
        </div>
      )}
    </div>
  );
}
