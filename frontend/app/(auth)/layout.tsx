import Sidebar from "@/components/layout/Sidebar";
import { AuthProvider } from "@/lib/auth-context";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Sidebar />
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {children}
      </main>
    </AuthProvider>
  );
}
