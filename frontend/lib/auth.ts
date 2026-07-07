import type { Role, UserProfile } from "@/lib/types";

export const PUBLIC_PATHS = ["/login", "/acesso-negado", "/auth/callback", "/offline"];
export const PUBLIC_API_PATHS = ["/api/auth/login"];

type RouteRule = {
  pattern: RegExp;
  roles: Role[];
};

const ALL: Role[] = ["master_dev", "admin", "gestor", "representante"];
const ELEVATED: Role[] = ["master_dev", "admin"];
const GESTOR_UP: Role[] = ["master_dev", "admin", "gestor"];
const DEV_ONLY: Role[] = ["master_dev"];
const DISABLED: Role[] = [];

// Primeiro match ganha. Rotas mais restritivas devem vir primeiro.
export const ROUTE_RULES: RouteRule[] = [
  { pattern: /^\/admin\/usuarios\/novo\/?$/, roles: GESTOR_UP },
  { pattern: /^\/admin\/usuarios\/?$/, roles: GESTOR_UP },
  { pattern: /^\/admin/,            roles: ELEVATED },
  { pattern: /^\/agente-studio/,    roles: ELEVATED },
  { pattern: /^\/ia-secretaria/,    roles: ALL },
  { pattern: /^\/conexao/,          roles: ALL },
  { pattern: /^\/revisaopedido/,    roles: DISABLED },
  { pattern: /^\/pedidos\/monitor/, roles: GESTOR_UP },
  { pattern: /^\/produtos/,         roles: ALL },
  { pattern: /^\/tabela-preco/,     roles: ALL },
  { pattern: /^\/saida-produtos/,   roles: ALL },
  { pattern: /^\/resultados/,       roles: GESTOR_UP },
  { pattern: /^\/conversas-secretaria/, roles: DEV_ONLY },
  { pattern: /^\/log-secretaria/,   roles: DEV_ONLY },
  { pattern: /^\/logs\/clic-vendas/, roles: DEV_ONLY },
  { pattern: /^\/logs/,             roles: GESTOR_UP },
  { pattern: /^\/pedidos/,          roles: ALL },
  { pattern: /^\/clientes/,         roles: ALL },
  { pattern: /^\/recorrencia/,      roles: ALL },
  { pattern: /^\/ativacao/,         roles: ALL },
  { pattern: /^\/baixar-app/,       roles: ALL },
  { pattern: /^\/perfil/,           roles: ALL },
];

export const API_ROUTE_RULES: RouteRule[] = [
  { pattern: /^\/api\/admin\/usuarios/, roles: GESTOR_UP },
  { pattern: /^\/api\/admin/,          roles: ELEVATED },
  { pattern: /^\/api\/agente-studio/,  roles: ELEVATED },
  { pattern: /^\/api\/secretaria\/conversas/, roles: DEV_ONLY },
  { pattern: /^\/api\/secretaria/,     roles: ALL },
  { pattern: /^\/api\/conexao/,        roles: ALL },
  { pattern: /^\/api\/revisaopedido/,  roles: DISABLED },
  { pattern: /^\/api\/settings/,       roles: ELEVATED },
  { pattern: /^\/api\/pedidos\/cron/,  roles: ELEVATED },
  { pattern: /^\/api\/pedidos\/sync/,  roles: GESTOR_UP },
  { pattern: /^\/api\/produtos/,       roles: ALL },
  { pattern: /^\/api\/tabela-preco/,   roles: ALL },
  { pattern: /^\/api\/saida-produtos/, roles: ALL },
  { pattern: /^\/api\/resultados/,     roles: GESTOR_UP },
  { pattern: /^\/api\/logs\/clic-vendas/, roles: DEV_ONLY },
  { pattern: /^\/api\/logs/,           roles: GESTOR_UP },
  { pattern: /^\/api\/pedidos/,        roles: ALL },
  { pattern: /^\/api\/clientes/,       roles: ALL },
  { pattern: /^\/api\/recorrencia/,    roles: ALL },
  { pattern: /^\/api\/ativacao/,       roles: ALL },
  { pattern: /^\/api\/perfil/,         roles: ALL },
  { pattern: /^\/api\/status/,         roles: ALL },
];

export function canAccess(profile: UserProfile | null, pathname: string): boolean {
  if (!profile || !profile.ativo) return false;
  const rule = ROUTE_RULES.find((r) => r.pattern.test(pathname));
  if (!rule) return true;
  return rule.roles.includes(profile.role);
}

export function isMasterOrAdmin(profile: UserProfile | null): boolean {
  return profile?.role === "master_dev" || profile?.role === "admin";
}

export function isRepresentante(profile: UserProfile | null): boolean {
  return profile?.role === "representante";
}

// Itens de nav com seus roles permitidos — único source of truth para a Sidebar
export const NAV_ITEMS = [
  { href: "/pedidos",        label: "Pedidos",          roles: ALL },
  { href: "/clientes",       label: "Clientes",         roles: ALL },
  { href: "/recorrencia",    label: "Recorrência",      roles: ALL },
  { href: "/ativacao",       label: "Ativação",         roles: ALL },
  { href: "/baixar-app",     label: "Baixar APP",       roles: ALL },
  { href: "/saida-produtos", label: "Saída de Produtos", roles: ALL },
  { href: "/resultados",     label: "Resultados",       roles: GESTOR_UP },
  { href: "/logs",           label: "Logs de Disparo",  roles: GESTOR_UP },
  { href: "/conversas-secretaria", label: "Conversas Secretaria", roles: DEV_ONLY },
  { href: "/log-secretaria", label: "Log Secretaria",   roles: DEV_ONLY },
  { href: "/produtos",       label: "Produtos",         roles: ALL },
  { href: "/tabela-preco",   label: "Tabela de Preço",  roles: ALL },
  { href: "/conexao",        label: "Conexão",          roles: ALL },
  { href: "/ia-secretaria",  label: "IA Secretária",    roles: ALL },
  { href: "/agente-studio",  label: "Agente Studio",    roles: ELEVATED },
  { href: "/admin/usuarios", label: "Usuários",         roles: GESTOR_UP },
  { href: "/perfil",         label: "Meu Perfil",       roles: ALL },
] as const;
