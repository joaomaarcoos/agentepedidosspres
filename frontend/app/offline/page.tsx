export default function OfflinePage() {
  return (
    <main className="offline-page">
      <div className="offline-card">
        <div className="offline-brand">
          Agente<span>Pedidos</span>
        </div>
        <h1>Sem conexao</h1>
        <p>Verifique a internet e tente novamente. As areas do sistema precisam da API online para carregar os dados.</p>
        <a href="/pedidos">Tentar abrir novamente</a>
      </div>
    </main>
  );
}
