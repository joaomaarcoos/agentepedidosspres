"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

type ShellContextValue = {
  sidebarCollapsed: boolean;
  mobileMenuOpen: boolean;
  closeMobileMenu: () => void;
  toggleSidebar: () => void;
};

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const closeMobileMenu = useCallback(() => setMobileMenuOpen(false), []);
  const toggleSidebar = useCallback(() => {
    if (window.matchMedia("(max-width: 760px)").matches) {
      setMobileMenuOpen((open) => !open);
      return;
    }
    setSidebarCollapsed((collapsed) => !collapsed);
  }, []);

  const value = useMemo<ShellContextValue>(
    () => ({
      sidebarCollapsed,
      mobileMenuOpen,
      closeMobileMenu,
      toggleSidebar,
    }),
    [closeMobileMenu, mobileMenuOpen, sidebarCollapsed, toggleSidebar]
  );

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell() {
  const value = useContext(ShellContext);
  if (!value) {
    return {
      sidebarCollapsed: false,
      mobileMenuOpen: false,
      closeMobileMenu: () => undefined,
      toggleSidebar: () => undefined,
    };
  }
  return value;
}
