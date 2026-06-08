import type { Metadata, Viewport } from "next";
import "./globals.css";
import PwaRegister from "@/components/PwaRegister";
import PwaInstallPrompt from "@/components/PwaInstallPrompt";

const SUCOS_SPRES_LOGO_URL =
  "https://tsnvhhrifxcnuszzaxfk.supabase.co/storage/v1/object/public/app-assets/brand/sucos-spres-logo.png";

export const metadata: Metadata = {
  title: "AgentePedidos",
  description: "SucosSpres - ClicVendas fullstack com modulos internos em Python",
  applicationName: "IA Sales Spres",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "IA Sales Spres",
  },
  formatDetection: {
    telephone: false,
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
  icons: {
    icon: [{ url: SUCOS_SPRES_LOGO_URL, type: "image/png" }],
    shortcut: [{ url: SUCOS_SPRES_LOGO_URL, type: "image/png" }],
    apple: [{ url: SUCOS_SPRES_LOGO_URL, type: "image/png" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0b10",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        {children}
        <PwaRegister />
        <PwaInstallPrompt />
      </body>
    </html>
  );
}
