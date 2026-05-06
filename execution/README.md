# Execution

Este diretorio contem apenas os scripts Python ainda usados pelo fluxo oficial.

## Fluxo atual
1. `clic_vendas_cli.py` expoe os comandos internos chamados pelo Next.js via `spawn`.
2. `clic_vendas_client.py` encapsula a autenticacao e chamadas HTTP da API ClicVendas.
3. `fetch_pedidos_clic.py` normaliza pedidos retornados pela API externa.
4. `conexao_cli.py` verifica configuracao e autentica o modulo Conexao.
5. `clientes_cli.py` sincroniza e lista clientes via `/extpessoas`.
6. `recorrencia_cli.py` calcula recorrencia a partir dos pedidos ja sincronizados.
7. `supabase_client.py` persiste pedidos, clientes e logs em Supabase ou em `.tmp/data/`.

## Escopo
- Nao existe mais servidor Python separado.
- Nao existe mais FastAPI, Uvicorn ou `hub.py`.
- O modulo Python roda apenas como script interno acionado pelas rotas `app/api` do Next.js.

## Principios
- Scripts devem ser deterministas e com responsabilidade clara.
- Variaveis sensiveis vem do `.env`.
- Tudo em `.tmp/` pode ser recriado.
