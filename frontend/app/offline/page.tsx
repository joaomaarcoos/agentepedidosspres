const SUCOS_SPRES_LOGO_URL =
  "https://tsnvhhrifxcnuszzaxfk.supabase.co/storage/v1/object/public/app-assets/brand/sucos-spres-logo.png";

export default function OfflinePage() {
  return (
    <main className="offline-page">
      <div className="offline-card">
        <div className="offline-brand">
          <img src={SUCOS_SPRES_LOGO_URL} alt="Sucos Spres" />
          <span>AgentePedidos</span>
        </div>
        <h1>Sem conexao</h1>
        <p>Verifique a internet e tente novamente. As areas do sistema precisam da API online para carregar os dados.</p>
        <a href="/pedidos">Tentar abrir novamente</a>
      </div>
    </main>
  );
}
