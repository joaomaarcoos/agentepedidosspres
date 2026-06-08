"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart2,
  BrainCircuit,
  ClipboardCheck,
  Download,
  FileText,
  LogOut,
  Package,
  Repeat2,
  Settings2,
  ShoppingCart,
  Tag,
  TrendingUp,
  User,
  Users,
  Zap,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { NAV_ITEMS } from "@/lib/auth";

const ICON_MAP: Record<string, React.ElementType> = {
  "/pedidos": ShoppingCart,
  "/clientes": Users,
  "/recorrencia": Repeat2,
  "/ativacao": Zap,
  "/baixar-app": Download,
  "/previsao": TrendingUp,
  "/resultados": BarChart2,
  "/logs": FileText,
  "/produtos": Package,
  "/tabela-preco": Tag,
  "/revisaopedido": ClipboardCheck,
  "/conexao": Activity,
  "/agente-studio": BrainCircuit,
  "/admin/usuarios": Settings2,
  "/perfil": User,
};

const ROLE_LABEL: Record<string, string> = {
  master_dev: "Master Dev",
  admin: "Admin",
  gestor: "Gestor",
  representante: "Representante",
};

export default function Sidebar() {
  const pathname = usePathname();
  const { profile, loading, signOut } = useAuth();

  const visibleNav = profile
    ? NAV_ITEMS.filter((item) => (item.roles as readonly string[]).includes(profile.role))
    : [];

  return (
    <>
      <aside className="desktop-sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">A</div>
          <div>
            <div className="sidebar-title">
              Agente<span>Pedidos</span>
            </div>
            <div className="sidebar-subtitle">SucosSpres</div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Navegacao principal">
          {loading ? (
            <div className="sidebar-loading">Carregando...</div>
          ) : (
            visibleNav.map(({ href, label }) => {
              const Icon = ICON_MAP[href] || ShoppingCart;
              const isActive = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link key={href} href={href} className={`sidebar-link${isActive ? " is-active" : ""}`}>
                  <Icon size={16} />
                  {label}
                </Link>
              );
            })
          )}
        </nav>

        <div className="sidebar-user">
          {profile && (
            <div className="sidebar-user-meta">
              <div className="sidebar-user-name">{profile.nome}</div>
              <div className="sidebar-user-role">{ROLE_LABEL[profile.role] ?? profile.role}</div>
            </div>
          )}
          <button className="sidebar-logout" onClick={signOut}>
            <LogOut size={13} />
            Sair
          </button>
        </div>
      </aside>

      <nav className="mobile-tabbar" aria-label="Navegacao principal">
        {loading ? (
          <span className="mobile-tabbar-loading">Carregando...</span>
        ) : (
          visibleNav.map(({ href, label }) => {
            const Icon = ICON_MAP[href] || ShoppingCart;
            const isActive = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={`mobile-tabbar-item${isActive ? " is-active" : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon size={18} />
                <span>{label}</span>
              </Link>
            );
          })
        )}
      </nav>
    </>
  );
}
