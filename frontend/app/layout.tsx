import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";

export const metadata: Metadata = {
  title: "AgentePedidos",
  description: "SucosSpres - ClicVendas fullstack com modulos internos em Python",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        <Sidebar />
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
