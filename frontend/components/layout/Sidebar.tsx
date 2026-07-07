"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  BarChart2,
  Bot,
  BrainCircuit,
  Download,
  FileText,
  MessageSquareText,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
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
import { useShell } from "@/components/layout/ShellContext";

const SUCOS_SPRES_LOGO_URL =
  "https://tsnvhhrifxcnuszzaxfk.supabase.co/storage/v1/object/public/app-assets/brand/sucos-spres-logo.png";

const ICON_MAP: Record<string, React.ElementType> = {
  "/pedidos": ShoppingCart,
  "/clientes": Users,
  "/recorrencia": Repeat2,
  "/ativacao": Zap,
  "/baixar-app": Download,
  "/saida-produtos": TrendingUp,
  "/resultados": BarChart2,
  "/logs": FileText,
  "/conversas-secretaria": MessageSquareText,
  "/log-secretaria": FileText,
  "/produtos": Package,
  "/tabela-preco": Tag,
  "/conexao": Activity,
  "/ia-secretaria": Bot,
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

const MENU_SECTIONS = [
  { type: "link", href: "/resultados" },
  {
    type: "group",
    label: "Vendas",
    items: ["/pedidos", "/recorrencia", "/ativacao", "/saida-produtos"],
  },
  {
    type: "group",
    label: "Cadastros",
    items: ["/clientes", "/produtos", "/tabela-preco"],
  },
  {
    type: "group",
    label: "AI",
    items: ["/ia-secretaria", "/agente-studio"],
  },
  {
    type: "group",
    label: "Configurações",
    items: ["/admin/usuarios", "/perfil", "/baixar-app", "/conexao", "/logs", "/conversas-secretaria", "/log-secretaria"],
  },
] as const;

function findActiveGroup(pathname: string) {
  const activeGroup = MENU_SECTIONS.find(
    (section) =>
      section.type === "group" &&
      section.items.some((href) => pathname === href || pathname.startsWith(`${href}/`))
  );
  return activeGroup?.type === "group" ? activeGroup.label : null;
}

export default function Sidebar() {
  const pathname = usePathname();
  const { profile, loading, signOut } = useAuth();
  const { closeMobileMenu, mobileMenuOpen, sidebarCollapsed, toggleSidebar } = useShell();
  const [openSections, setOpenSections] = useState<Set<string>>(() => {
    const activeGroup = findActiveGroup(pathname);
    return new Set(activeGroup ? [activeGroup] : ["Vendas"]);
  });

  const visibleNav = profile
    ? NAV_ITEMS.filter((item) => (item.roles as readonly string[]).includes(profile.role))
    : [];
  const visibleByHref = new Map(visibleNav.map((item) => [item.href, item]));

  useEffect(() => {
    closeMobileMenu();
  }, [closeMobileMenu, pathname]);

  useEffect(() => {
    const activeGroup = findActiveGroup(pathname);
    if (!activeGroup) return;
    setOpenSections((current) => {
      if (current.has(activeGroup)) return current;
      const next = new Set(current);
      next.add(activeGroup);
      return next;
    });
  }, [pathname]);

  function toggleSection(label: string) {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  }

  return (
    <>
      {mobileMenuOpen && <button className="sidebar-scrim" aria-label="Fechar menu" onClick={closeMobileMenu} />}
      <aside className={`desktop-sidebar${sidebarCollapsed ? " is-collapsed" : ""}${mobileMenuOpen ? " is-open" : ""}`}>
        <div className="sidebar-brand">
          <img className="sidebar-logo" src={SUCOS_SPRES_LOGO_URL} alt="Sucos Spres" />
          <div className="sidebar-brand-copy">
            <div className="sidebar-title">
              Agente<span>Pedidos</span>
            </div>
            <div className="sidebar-subtitle">SucosSpres</div>
          </div>
          <button className="sidebar-toggle" onClick={toggleSidebar} aria-label="Expandir ou ocultar menu">
            {sidebarCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>

        <nav className="sidebar-nav" aria-label="Navegacao principal">
          {loading ? (
            <div className="sidebar-loading">Carregando...</div>
          ) : (
            MENU_SECTIONS.map((section) => {
              if (section.type === "link") {
                const item = visibleByHref.get(section.href);
                if (!item) return null;
                const Icon = ICON_MAP[item.href] || ShoppingCart;
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`sidebar-link sidebar-primary-link${isActive ? " is-active" : ""}`}
                  >
                    <Icon size={16} />
                    <span className="sidebar-link-label">{item.label}</span>
                  </Link>
                );
              }

              const items = section.items
                .map((href) => visibleByHref.get(href))
                .filter((item): item is NonNullable<typeof item> => Boolean(item));

              if (items.length === 0) return null;
              const isOpen = openSections.has(section.label);

              return (
                <div className="sidebar-section" key={section.label}>
                  <button
                    className="sidebar-section-toggle"
                    onClick={() => toggleSection(section.label)}
                    aria-expanded={isOpen}
                  >
                    <span className="sidebar-section-title">{section.label}</span>
                    <span className="sidebar-section-chevron">{isOpen ? "−" : "+"}</span>
                  </button>
                  {isOpen && (
                    <div className="sidebar-subnav">
                      {items.map(({ href, label }) => {
                        const Icon = ICON_MAP[href] || ShoppingCart;
                        const isActive = pathname === href || pathname.startsWith(`${href}/`);
                        return (
                          <Link
                            key={href}
                            href={href}
                            className={`sidebar-link sidebar-child-link${isActive ? " is-active" : ""}`}
                          >
                            <Icon size={15} />
                            <span className="sidebar-link-label">{label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
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
            <span className="sidebar-link-label">Sair</span>
          </button>
        </div>
      </aside>
    </>
  );
}
