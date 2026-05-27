import Link from "next/link";

export default function NotFoundPage() {
  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg)",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontSize: 64,
            fontWeight: 800,
            color: "var(--muted)",
            marginBottom: 12,
            lineHeight: 1,
          }}
        >
          404
        </div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "var(--text)",
            marginBottom: 8,
          }}
        >
          Página não encontrada
        </div>
        <div
          style={{
            fontSize: 14,
            color: "var(--muted)",
            marginBottom: 32,
            maxWidth: 320,
            lineHeight: 1.6,
          }}
        >
          O endereço acessado não existe ou foi movido.
        </div>
        <Link
          href="/pedidos"
          style={{
            display: "inline-block",
            padding: "10px 24px",
            background: "var(--accent)",
            color: "#fff",
            borderRadius: 8,
            textDecoration: "none",
            fontSize: 14,
            fontWeight: 600,
            boxShadow: "0 0 14px var(--accent-glow)",
          }}
        >
          Ir para Pedidos
        </Link>
      </div>
    </div>
  );
}
