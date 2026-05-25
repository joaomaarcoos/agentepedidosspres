import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentePedidos",
  description: "SucosSpres - ClicVendas fullstack com modulos internos em Python",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        {children}
      </body>
    </html>
  );
}
