import Sidebar from "@/components/layout/Sidebar";
import { ShellProvider } from "@/components/layout/ShellContext";
import { AuthProvider } from "@/lib/auth-context";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ShellProvider>
        <div className="app-shell">
          <Sidebar />
          <main className="app-main">{children}</main>
        </div>
      </ShellProvider>
    </AuthProvider>
  );
}
