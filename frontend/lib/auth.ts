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

// Primeiro match ganha. Rotas mais restritivas devem vir primeiro.
export const ROUTE_RULES: RouteRule[] = [
  { pattern: /^\/admin/,            roles: ELEVATED },
  { pattern: /^\/agente-studio/,    roles: ELEVATED },
  { pattern: /^\/conexao/,          roles: ELEVATED },
  { pattern: /^\/revisaopedido/,    roles: ELEVATED },
  { pattern: /^\/pedidos\/monitor/, roles: GESTOR_UP },
  { pattern: /^\/produtos/,         roles: GESTOR_UP },
  { pattern: /^\/tabela-preco/,     roles: GESTOR_UP },
  { pattern: /^\/previsao/,         roles: GESTOR_UP },
  { pattern: /^\/resultados/,       roles: GESTOR_UP },
  { pattern: /^\/logs/,             roles: GESTOR_UP },
  { pattern: /^\/pedidos/,          roles: ALL },
  { pattern: /^\/clientes/,         roles: ALL },
  { pattern: /^\/recorrencia/,      roles: ALL },
  { pattern: /^\/ativacao/,         roles: ALL },
  { pattern: /^\/perfil/,           roles: ALL },
];

export const API_ROUTE_RULES: RouteRule[] = [
  { pattern: /^\/api\/admin/,          roles: ELEVATED },
  { pattern: /^\/api\/agente-studio/,  roles: ELEVATED },
  { pattern: /^\/api\/conexao/,        roles: ELEVATED },
  { pattern: /^\/api\/revisaopedido/,  roles: ELEVATED },
  { pattern: /^\/api\/settings/,       roles: ELEVATED },
  { pattern: /^\/api\/pedidos\/cron/,  roles: ELEVATED },
  { pattern: /^\/api\/pedidos\/sync/,  roles: GESTOR_UP },
  { pattern: /^\/api\/produtos/,       roles: GESTOR_UP },
  { pattern: /^\/api\/tabela-preco/,   roles: GESTOR_UP },
  { pattern: /^\/api\/previsao/,       roles: GESTOR_UP },
  { pattern: /^\/api\/resultados/,     roles: GESTOR_UP },
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
  { href: "/previsao",       label: "Previsão",         roles: GESTOR_UP },
  { href: "/resultados",     label: "Resultados",       roles: GESTOR_UP },
  { href: "/logs",           label: "Logs Disparos",    roles: GESTOR_UP },
  { href: "/produtos",       label: "Produtos",         roles: GESTOR_UP },
  { href: "/tabela-preco",   label: "Tabela de Preço",  roles: GESTOR_UP },
  { href: "/revisaopedido",  label: "Revisão Pedidos",  roles: ELEVATED },
  { href: "/conexao",        label: "Conexão",          roles: ELEVATED },
  { href: "/agente-studio",  label: "Agente Studio",    roles: ELEVATED },
  { href: "/admin/usuarios", label: "Usuários",         roles: ELEVATED },
  { href: "/perfil",         label: "Meu Perfil",       roles: ALL },
] as const;
