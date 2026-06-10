# Auditoria Tecnica Completa do AgentePedidos

Data da auditoria: 10 de junho de 2026  
Escopo: codigo, frontend, APIs, Python, IA, WhatsApp, Supabase, seguranca, testes, deploy e operacao.

## 1. Resumo executivo

O sistema possui uma base funcional relevante: o build de producao passa, 54 testes Python passam, o webhook de audio esta operacional apos a correcao recente, o banco real tem RLS habilitado nas tabelas inspecionadas e as principais telas possuem rotas correspondentes.

Entretanto, a auditoria encontrou riscos que impedem tratar o sistema como operacionalmente seguro e totalmente conectado:

1. A policy de autoedicao de perfil permite escalada de privilegio diretamente pelo Supabase.
2. O projeto usa uma versao do Next.js com vulnerabilidade critica de bypass de middleware.
3. Representantes nao estao isolados por carteira em recorrencia, ativacao e revisao de pedidos.
4. O pipeline de ativacao termina na aprovacao da IA e nao envia mensagem.
5. O painel de resultados depende de estados de conversao que nenhum modulo produz.
6. Pedidos, clientes e recorrencia usam duas fontes de pedidos que nao sao sincronizadas pelo mesmo fluxo.
7. Fallbacks locais em producao podem confirmar pedidos que ficam invisiveis no Supabase.
8. O scheduler interpreta incorretamente o envelope retornado pelo Python.
9. A sincronizacao de tabela de preco pode apagar dados validos antes de concluir a reposicao.
10. O schema versionado nao reproduz o banco real e nao contem migrations de tabelas centrais.

### Classificacao geral

| Dominio | Estado | Risco |
|---|---|---|
| Autenticacao | Funcional | Critico |
| Autorizacao/RBAC | Parcial | Critico |
| Pedidos ClicVendas | Parcial | Alto |
| Clientes | Desconectado da fonte oficial | Alto |
| Recorrencia | Parcialmente funcional | Alto |
| Ativacao | Incompleto | Critico |
| Resultados | Sem produtores completos | Critico |
| IA/WhatsApp | Funcional com riscos de consistencia | Alto |
| Revisao de pedidos | Funcional sem ownership persistido | Critico |
| Produtos | Funcional | Medio |
| Tabela de preco | Funcional com risco destrutivo | Critico |
| Supabase/schema | Producao protegida, migrations incompletas | Alto |
| Cron/jobs | Fragil | Alto |
| Testes/CI | Cobertura concentrada | Alto |
| Deploy/observabilidade | Basico | Alto |

## 2. Metodologia e validacoes executadas

A auditoria combinou cinco revisoes independentes por subagentes:

- backend e integracoes comerciais;
- frontend, APIs e contratos;
- seguranca;
- IA, WhatsApp e revisao de pedidos;
- testes, migrations, deploy e observabilidade.

Validacoes locais:

- `py -m unittest discover -s tests -v`: 54 testes aprovados;
- `npm run build`: build Next.js aprovado;
- `npm run lint`: nao executavel de forma automatica, pois abre configuracao interativa;
- `npm audit --prefix frontend`: uma vulnerabilidade critica e uma moderada;
- consulta somente leitura ao schema real do Postgres;
- consulta de integridade e contagens das tabelas principais;
- inspecao dos contratos entre rotas Next.js, bridge Python e CLIs.

### Estado observado no banco em 10/06/2026

- `recurrence_targets`: 38 registros;
- recorrencia: 23 `ai_approved`, 10 `candidate`, 3 `dispatched`, 2 `ai_rejected`;
- `message_events`: 6 eventos, todos outbound/text nos ultimos 30 dias;
- `ai_conversations`: 22;
- `ai_conversation_messages`: 99;
- `pedidos_revisao`: 9;
- `rep_order_base`: 188;
- `clic_clientes`: 104;
- 19 conversas sem mensagens;
- nenhuma mensagem orfa;
- nenhum pedido em revisao sem conversa;
- nenhum sync preso em `running` por mais de uma hora.

Todas as tabelas inspecionadas no banco real estavam com RLS habilitado. Somente `user_profiles` possuia policies. Nas demais, a ausencia de policy bloqueia acesso por `anon` e `authenticated`, enquanto a service role continua operando.

## 3. Achados criticos

### SEC-01 - Escalada de privilegio pelo Supabase

**Evidencia:** `execution/auth_migration.sql:49-58`.

A policy `user_profiles: self update` permite atualizar a linha inteira do proprio usuario. PostgreSQL RLS restringe linhas, nao colunas. Um representante autenticado pode usar a API REST do Supabase para alterar `role`, `ativo` e `cod_rep`, contornando as validacoes das APIs Next.js.

A policy administrativa tambem permite que admin altere qualquer coluna diretamente, incluindo promocao para `master_dev`, sem as regras implementadas nos handlers.

**Impacto:** controle administrativo, acesso cruzado entre carteiras e modificacao de usuarios.

**Correcao recomendada:**

1. Remover as policies genericas de `UPDATE`.
2. Revogar update direto de `authenticated`.
3. Criar RPCs `SECURITY DEFINER` separadas para editar apenas nome/CPF e para administracao.
4. Validar role do executor e campos permitidos dentro das funcoes.
5. Criar testes que tentem alterar `role`, `ativo` e `cod_rep` via cliente autenticado.

### SEC-02 - Next.js vulneravel a bypass de middleware

**Evidencia:** `frontend/package.json:17`.

O projeto fixa `next@14.2.3`. O audit identificou, entre outras, a vulnerabilidade critica `GHSA-f82v-jwr5-mffw`, relacionada a bypass de middleware. A atual arquitetura usa o middleware como primeira fronteira de autorizacao.

As rotas atuais tambem chamam `requireApiRole`, o que reduz o impacto em APIs, mas paginas e futuras rotas podem ficar expostas se dependerem apenas do middleware.

**Correcao recomendada:** atualizar imediatamente para pelo menos `14.2.35`, executar build e testes, e manter autorizacao dentro de cada handler.

### AUTH-01 - Falta de isolamento por representante

**Evidencias:**

- `frontend/app/api/recorrencia/route.ts:13-34`;
- `execution/recorrencia_cli.py:466-484`;
- `frontend/app/api/ativacao/route.ts:15-31`;
- `execution/ativacao_cli.py:215-272`;
- `frontend/app/api/revisaopedido/route.ts:8-18`;
- `frontend/app/api/revisaopedido/[id]/route.ts:8-39`;
- `execution/revisaopedido_cli.py:225-287`.

Pedidos e clientes normais aplicam `cod_rep` quando o usuario e representante. Recorrencia, ativacao e revisao de pedidos nao fazem isso.

Um representante pode:

- listar CPFs, telefones e historico comercial de outras carteiras;
- abrir detalhes de qualquer target conhecido;
- ler conversas completas vinculadas a pedidos;
- editar itens e observacoes;
- alterar status de pedidos de outro representante.

**Correcao recomendada:**

1. Persistir `cod_rep` em `pedidos_revisao`.
2. Passar `cod_rep` autenticado para todos os CLIs.
3. Aplicar filtro em listagem, detalhe, edicao e status.
4. Retornar 404, nao 403, para IDs fora da carteira.
5. Implementar policies/RPCs de ownership no banco.

### FLOW-01 - Pipeline de ativacao sem disparo

**Evidencias:**

- `execution/agent_validacao_ativacao.py:167-213`;
- `frontend/lib/server/ativacao.ts:71-81`;
- `execution/disparos_recorrencia.py:172-178`.

O validador grava `activation_approved`. O pipeline Next.js executa somente geracao e validacao. O unico despachante busca apenas `status='ai_approved'` e `target_type='recorrencia'`.

Portanto, uma ativacao aprovada nao possui consumidor e nunca chega ao WhatsApp.

**Correcao recomendada:** criar um despachante de ativacao ou generalizar o despachante existente por `target_type`, com template, configuracao, log e idempotencia proprios.

### FLOW-02 - Resultados e conversoes sem produtores

**Evidencias:**

- `execution/resultados_cli.py:49-116`;
- `execution/recorrencia_cli.py:493-500`.

O painel de resultados le `dispatched`, `converted` e `converted_order_value`. Nao existe modulo que:

- marque uma resposta como `responded`;
- associe um novo pedido a um target disparado;
- altere o target para `converted`;
- preencha numero e valor convertido.

O resultado atual mede apenas mensagens enviadas. Receita e taxa de conversao permanecem incompletas.

**Correcao recomendada:** criar reconciliador de conversao, usando telefone/CPF, data de disparo e pedidos posteriores, com janela, confianca e auditoria.

### DATA-01 - Fontes de pedido desconectadas

**Evidencias:**

- sync oficial grava `rep_order_base`: `execution/clic_vendas_cli.py:179`;
- clientes le `clic_pedidos_integrados`: `execution/clientes_cli.py:127`;
- recorrencia le `clic_pedidos_integrados`: `execution/recorrencia_cli.py:265`.

O sistema mantem dois modelos de pedidos. O fluxo oficial de sincronizacao nao atualiza `clic_pedidos_integrados`, mas clientes e recorrencia dependem dela.

Isso explica por que modulos podem apresentar dados divergentes mesmo apos “Atualizar Base”.

**Correcao recomendada:** escolher uma unica fonte canonica. A opcao mais simples e migrar clientes e recorrencia para `rep_order_base`, enriquecendo-a ou criando views normalizadas.

### DATA-02 - Fallback local confirma operacoes invisiveis

**Evidencias:**

- `execution/ai_agent.py:2153-2272`;
- `execution/ai_agent.py:2404-2541`;
- `execution/supabase_client.py:63-68`.

Em falhas do Supabase, diversos componentes passam para JSON local. Em producao isso cria split-brain:

- o cliente pode receber confirmacao de pedido;
- o pedido fica apenas no volume `.tmp`;
- painel, APIs e outro container consultam Supabase e nao veem o registro;
- idempotencia deixa de ser distribuida.

**Correcao recomendada:** permitir fallback somente com `APP_ENV=development`. Em producao, falhar fechado, registrar incidente e nao confirmar operacoes persistentes ao cliente.

### PRICE-01 - Atualizacao destrutiva da tabela de preco

**Evidencia:** `execution/tabela_preco_cli.py:255-276`.

O sync apaga todos os itens das tabelas selecionadas antes de inserir os novos lotes. Nao existe transacao entre delete e inserts. Qualquer falha de rede, schema ou lote deixa a tabela vazia ou parcial.

**Correcao recomendada:** carregar em tabela staging com `sync_run_id`, validar contagem e nomes, e trocar os dados em uma unica transacao/RPC.

## 4. Achados altos

### JOB-01 - Scheduler interpreta o envelope Python incorretamente

**Evidencia:** `frontend/lib/server/cron-scheduler.ts:60-75`.

`runPythonJson` retorna `{ok, data}`, mas o scheduler tipa o retorno como se `status` e `message` estivessem na raiz. Uma execucao bem-sucedida tende a ser registrada como erro e a mensagem fica `undefined`.

### JOB-02 - Scheduler local, sem lock e sem coordenacao

**Evidencia:** `frontend/lib/server/cron-scheduler.ts:19-85`.

O scheduler usa `setInterval` e `.tmp/cron_settings.json`.

Riscos:

- reinicio perde o instante correto;
- multiplas replicas executam o mesmo job;
- nao existe lock;
- configuracao depende de volume local;
- erros de leitura retornam configuracao default silenciosamente.

Mover para cron externo ou job persistido com claim atomico.

### JOB-03 - Intervalo do cron sem validacao

**Evidencia:** `frontend/app/api/pedidos/cron/route.ts:16-20`.

Zero, numero negativo, infinito ou `NaN` podem ser persistidos e causar comportamento inesperado.

### DATA-03 - `clientes sync` nao sincroniza

**Evidencia:** `execution/clientes_cli.py:199-217`.

O comando percorre os clientes e monta objetos, mas nao grava nada. Retorna sucesso com `total_upserted: 0`. A UI chama isso de sincronizacao, embora seja apenas leitura.

Renomear para refresh/read ou implementar persistencia real.

### DATA-04 - Contrato de identificacao do cliente incompleto

**Evidencias:**

- `execution/clic_vendas_cli.py:83-118`;
- `execution/ai_agent.py:2836-2854`.

`clic_clientes` usa CPF/CNPJ como chave e nao persiste claramente `cod_cli`. O agente tenta usar `cod_cli`, CPF ou external ID para consultar `rep_order_base.cod_cli`, que e codigo interno numerico. O fallback para CPF pode produzir historico vazio ou consulta invalida.

Adicionar `cod_cli` explicito e constraint/indice.

### PRICE-02 - Paginacao SOAP provavelmente usa a contagem errada

**Evidencia:** `execution/tabela_preco_cli.py:206-208`.

`tem_mais` compara a quantidade de cabecalhos `tabelaPreco` com `PAGE_SIZE=300`. Os produtos ficam aninhados no cabecalho. Uma resposta com um cabecalho e centenas de itens pode ser tratada como ultima pagina.

Validar o contrato SOAP real e usar total/pagina retornado pelo servico ou a quantidade de produtos.

### PRICE-03 - Fallback silencioso para tabela 201

**Evidencias:** `execution/ai_agent.py:142-148`, `execution/ai_agent.py:3238-3248`.

Tabela desconhecida, ausente ou nao permitida cai para uma tabela padrao. Isso mantem o atendimento, mas pode cotar valores incorretos.

O fallback deve ser explicito na resposta ou bloquear precos/pedidos ate identificar a tabela correta.

### MSG-01 - Falha de envio perde a resposta definitivamente

**Evidencias:**

- entrada idempotente: `execution/ai_agent.py:3179-3187`;
- envio: `execution/evolution_webhook.py:454-461`.

A mensagem do usuario e marcada como processada antes do envio da resposta. Se a Evolution falhar apos a IA persistir a resposta, o retry do mesmo webhook vira duplicata e nao reenvia.

Implementar outbox com estados `pending`, `sending`, `sent`, `failed`, tentativas e chave idempotente.

### MSG-02 - Disparos de recorrencia podem duplicar

**Evidencias:** `execution/disparos_recorrencia.py:172-178`, `execution/disparos_recorrencia.py:241-268`.

Workers concorrentes podem selecionar o mesmo target, enviar e apenas depois marcar `dispatched`.

Usar claim atomico no banco (`FOR UPDATE SKIP LOCKED`, RPC ou update condicional).

### MSG-03 - Processamento do webhook e excessivamente sincrono

**Evidencias:**

- timeout de 90 segundos: `frontend/app/api/evolution/webhook/route.ts:81-85`;
- fluxo completo: `execution/evolution_webhook.py:430-461`.

Uma requisicao pode fazer download, transcricao, buffer, consultas, duas chamadas OpenAI, notificacao e varios envios. O processo pode ser encerrado depois de efeitos parciais.

O webhook deve validar, persistir evento e responder rapidamente. O processamento deve ocorrer em worker/fila.

### MSG-04 - Notificacao ao representante e best-effort

**Evidencia:** `execution/ai_agent.py:74-85`, `execution/ai_agent.py:3096`.

Falha de notificacao apenas gera log, mas o cliente recebe que o pedido foi enviado para revisao. Nao ha retry, status ou alerta.

### ORDER-01 - Ownership do pedido nao e persistido

**Evidencias:**

- schema: `execution/pedidos_revisao_migration.sql:2-18`;
- inferencia: `execution/review_order_whatsapp.py:154-183`.

`pedidos_revisao` nao possui `cod_rep`. O responsavel e recalculado a partir do historico mais recente. Mudancas de carteira podem alterar retroativamente quem enxerga/aprova o pedido.

### ORDER-02 - Maquina de estados permite regressao

**Evidencia:** `execution/revisaopedido_cli.py:260-276`.

Qualquer status valido pode substituir qualquer outro. Um pedido concluido pode voltar a pendente, mantendo `revisado_em`. Pelo WhatsApp, estados terminais tambem possuem transicoes conflitantes.

Definir transicoes permitidas e aplicar update condicional pelo estado anterior.

### ORDER-03 - Integracao automatica com ClicVendas e codigo morto

**Evidencia:** `execution/review_order_whatsapp.py:381-420`.

Existem funcoes para enviar pedido ao ClicVendas, mas nao possuem chamadores. A aprovacao apenas marca `pedido_feito` e presume lancamento manual. `clic_num_ped` nao e preenchido.

Decidir oficialmente entre fluxo manual e automatico; remover codigo morto ou concluir a integracao.

### SCHEMA-01 - Migrations nao reproduzem o banco real

O codigo depende de tabelas sem migration versionada no repositorio:

- `recurrence_targets`;
- `message_events`;
- `clic_clientes`;
- `clic_pedidos_integrados`;
- `tabelas_preco`;
- `tabelas_preco_itens`;
- possivelmente `representatives`.

O banco real possui varias delas, mas um ambiente novo nao pode ser reconstruido apenas com o Git.

### SCHEMA-02 - Migration ClicVendas falha em banco vazio

**Evidencia:** `execution/clic_vendas_migration.sql:22-66`.

O bloco tenta alterar `rep_order_base` antes do `CREATE TABLE IF NOT EXISTS`. Se a tabela nao existir, a migration aborta.

### SCHEMA-03 - Migrations versionadas omitem RLS das tabelas de negocio

O banco real esta com RLS habilitado, portanto nao ha exposicao direta confirmada hoje. Porem, os SQLs versionados de conversas, pedidos, produtos, logs e settings nao habilitam RLS.

Esse e um risco de reproducao/deploy, nao uma exposicao confirmada no banco atual.

## 5. Auditoria modulo por modulo

### 5.1 Autenticacao, usuarios e perfil

**Implementado:** login Supabase, callback, middleware, perfis, roles e administracao.

**Pontas soltas:**

- self-update de RLS permite alterar campos privilegiados;
- pagina e API de perfil permitem ao proprio usuario alterar `cod_rep`;
- gestores podem criar representantes, mas a listagem/detalhe de usuarios usa regras mais restritivas;
- senha minima de seis caracteres e fraca para perfis elevados;
- login nao possui rate limiting ou MFA.

**Prioridade:** primeira onda.

### 5.2 Pedidos e sincronizacao ClicVendas

**Implementado:** sync, logs, listagem, filtros por representante e previsao.

**Pontas soltas:**

- falhas de upsert podem retornar zero e ainda terminar como sucesso;
- scheduler le envelope incorreto;
- `rep_order_base` nao alimenta clientes/recorrencia;
- dependencias Python nao estao fixadas;
- nao ha testes do cliente HTTP, parsing, retry e persistencia.

### 5.3 Clientes

**Implementado:** listagem, detalhe, filtro por `cod_rep`.

**Pontas soltas:**

- depende de `clic_pedidos_integrados`, fora do sync oficial;
- botao/endpoint de sync nao grava;
- detalhe recebe `codCli`, mas internamente inicia busca usando string do parametro como CPF;
- identidade CPF versus codigo interno nao esta normalizada.

### 5.4 Recorrencia

**Implementado:** calculo, score, validacao IA, disparo, logs e UI.

**Pontas soltas:**

- fonte de pedidos separada;
- sem isolamento por representante;
- sem claim atomico;
- UI/tipos suportam `needs_review`, mas a API nao aceita esse status;
- 23 targets aprovados e apenas 3 disparados no estado observado, exigindo diagnostico operacional;
- nao existe produtor de `responded`/`converted`.

### 5.5 Ativacao

**Implementado:** criacao de candidatos, validacao IA, listagem e UI.

**Pontas soltas:**

- sem disparo;
- sem isolamento por representante;
- UI exibe contadores de disparados que o pipeline nao consegue produzir;
- resultados por ativacao permanecem vazios;
- falta diretiva e template operacional de envio equivalentes ao fluxo de recorrencia.

### 5.6 Resultados

**Implementado:** agregacao e tela.

**Pontas soltas:**

- modulo e somente leitor;
- conversoes nao sao reconciliadas;
- receita nao e produzida;
- taxa usa apenas estados finais existentes, nao uma coorte temporal;
- ativacao nao chega ao conjunto analisado.

### 5.7 Produtos

**Implementado:** catalogo base, busca e enriquecimento.

**Pontas soltas:**

- migration contém carga inicial manual que pode divergir do ERP;
- nomes da tabela de preco dependem do catalogo local;
- nao ha teste de integridade entre codigo, derivacao e nome;
- duas fontes de preco (`produtos` e `tabelas_preco_itens`) podem divergir.

### 5.8 Tabela de preco

**Implementado:** SOAP Senior, parse, enriquecimento, persistencia e UI.

**Pontas soltas:**

- delete antes de insert sem transacao;
- paginacao suspeita;
- sem migration versionada;
- sem versionamento/snapshot de tabela;
- fallback de preco silencioso;
- representantes podem ler todas as tabelas, sem avaliar necessidade comercial.

### 5.9 IA de atendimento e prompts

**Implementado:** classificacao, guardrails, subagente de catalogo, agente principal, tool de pedido e prompts modulares.

**Pontas soltas:**

- `ai_agent.py` concentra mais de 3.000 linhas e varias responsabilidades;
- saida do subagente e JSON livre, sem schema estrito;
- fallback local cria split-brain;
- chamadas OpenAI nao definem timeout explicito;
- custos, tokens e latencia nao sao registrados;
- tabela de preco fallback pode induzir resposta incorreta;
- prompt/contexto inclui grande volume de dados comerciais sem telemetria de tamanho.

### 5.10 Webhook, audio e Evolution

**Implementado:** autenticacao, base64, download de midia, Whisper, idempotencia de entrada e resposta.

**Pontas soltas:**

- segredo pode trafegar em query string;
- segredo global pode ser reutilizado por todas as instancias;
- resposta de criacao pode devolver URL contendo token;
- corpo e lido antes de limite de tamanho/rate limit;
- um processo Python e criado por webhook;
- grupos sao aceitos, mas a resposta e enviada para JID individual;
- fluxo `fromMe` precisa ser validado com payload real da Evolution;
- falha de envio nao possui outbox/retry.

### 5.11 Conexao e instancias

**Implementado:** criar, listar, QR code, reiniciar, desconectar, excluir e ligar/desligar agente.

**Pontas soltas:**

- qualquer role pode criar instancia;
- falha ao salvar ownership/token pode deixar instancia orfa;
- perfis elevados gerenciam todas as instancias;
- configuracao do agente e fail-open em indisponibilidade;
- token deveria ser por instancia, rotacionavel e armazenado com hash.

### 5.12 Revisao de pedidos

**Implementado:** painel, detalhe, edicao, status e comandos WhatsApp.

**Pontas soltas:**

- sem `cod_rep` persistido;
- sem ownership nas APIs;
- estados sem transicoes;
- comandos WhatsApp sem idempotencia propria;
- aprovacao nao cria pedido no ClicVendas;
- notificacao sem retry;
- ausencia de trilha de auditoria por alteracao.

### 5.13 Agente Studio

**Implementado:** CRUD de prompts e configuracao de buffer.

**Pontas soltas:**

- mudancas de prompt nao possuem versao, aprovacao ou rollback;
- arquivo e banco podem divergir;
- nao existe teste automatico antes de publicar prompt;
- um prompt invalido pode afetar todas as conversas imediatamente.

### 5.14 Logs e configuracoes

**Implementado:** logs de disparo, settings globais e telas.

**Pontas soltas:**

- configuracao pode cair para JSON local e nao propagar entre replicas;
- logs nao usam correlation ID;
- nao existe log estruturado central;
- dados pessoais aparecem em payloads e mensagens;
- nao ha politica de retencao.

### 5.15 Previsao

**Implementado:** usa pedidos sincronizados e aplica escopo por representante.

**Pontas soltas:**

- logica esta acoplada ao CLI de pedidos;
- nao ha testes estatisticos ou fixtures;
- ausencia de indicador de qualidade/amostra;
- resultado pode divergir de recorrencia, pois usam fontes diferentes.

### 5.16 Frontend, PWA e contratos

**Implementado:** paginas, shell, PWA, offline e cliente API central.

**Pontas soltas:**

- botoes aparecem para roles que receberao 403;
- status `needs_review` diverge entre UI e API;
- `Boolean("false")` pode ativar o agente;
- varias rotas devolvem erro interno bruto;
- ESLint nao esta configurado para CI;
- nao existem testes de componentes, rotas ou E2E.

### 5.17 Deploy e infraestrutura

**Implementado:** Docker multi-stage, compose, Swarm e Traefik.

**Pontas soltas:**

- container roda como root;
- sem healthcheck;
- `/api/status` nao testa banco, Python ou integracoes;
- script cria tag por commit, mas stack usa `latest`;
- deploy valida poucas variaveis obrigatorias;
- segredos ficam em environment, nao Docker Secrets;
- sem limites de CPU/memoria;
- sem rollback automatico;
- imagens base nao estao fixadas por digest.

### 5.18 Testes, CI e documentacao

**Estado atual:** 54 testes, concentrados em IA, prompts, webhook e WhatsApp.

**Sem cobertura relevante:**

- autenticacao/RLS;
- APIs e isolamento por representante;
- ClicVendas HTTP e sync;
- clientes;
- recorrencia;
- ativacao;
- disparos concorrentes;
- resultados/conversao;
- tabela de preco;
- migrations;
- cron;
- falhas e retries do Supabase/Evolution.

`CLAUDE.md` esta desatualizado: afirma que nao ha testes e que `/` redireciona para `/clic-vendas`, mas existem testes e o redirect atual e `/pedidos`.

## 6. Seguranca e privacidade

### Acoes imediatas

1. Corrigir RLS de `user_profiles`.
2. Atualizar Next.js.
3. Impedir autoedicao de `cod_rep`.
4. Implementar ownership por representante.
5. Rotacionar segredo global do webhook apos mudar o modelo.
6. Aplicar rate limit no login e webhook.
7. Sanitizar erros enviados ao cliente.

### Hardening recomendado

- usuario nao-root no container;
- filesystem read-only onde possivel;
- `cap_drop: ALL`;
- `no-new-privileges`;
- Docker Secrets;
- mascaramento de CPF/telefone em logs;
- politica LGPD de retencao e exclusao;
- CSP e headers de seguranca;
- MFA para `master_dev` e `admin`;
- auditoria de alteracoes administrativas.

## 7. Plano de trabalho recomendado

### Onda 0 - Contencao imediata

1. Corrigir policies de perfil.
2. Atualizar Next.js para 14.2.35 ou superior compativel.
3. Bloquear autoedicao de `cod_rep`.
4. Restringir revisao, recorrencia e ativacao por `cod_rep`.
5. Desabilitar fallback local em producao.

### Onda 1 - Fonte de verdade e schema

1. Escolher `rep_order_base` como fonte canonica ou justificar outra.
2. Migrar clientes e recorrencia.
3. Criar migrations completas de todas as tabelas.
4. Versionar policies, constraints, indices e funcoes.
5. Adicionar `cod_rep` em `pedidos_revisao`.

### Onda 2 - Concluir fluxos comerciais

1. Criar disparo de ativacao.
2. Criar reconciliacao de respostas e conversoes.
3. Definir integracao manual ou automatica com ClicVendas.
4. Corrigir sync de clientes.
5. Tornar sync de tabela de preco transacional.

### Onda 3 - Mensageria confiavel

1. Persistir eventos de webhook.
2. Criar fila/worker.
3. Implementar outbox de mensagens.
4. Claim atomico para disparos.
5. Retry com backoff e dead-letter.

### Onda 4 - Qualidade e operacao

1. Configurar ESLint nao interativo.
2. Adicionar CI com build, TypeScript, unittest, lint e audits.
3. Criar testes de API/RBAC/E2E.
4. Healthcheck real.
5. Logs estruturados, metricas, tracing e alertas.
6. Deploy por tag imutavel com rollback.

## 8. Backlog inicial priorizado

| ID | Tarefa | Prioridade | Esforco estimado |
|---|---|---:|---:|
| SEC-01 | Corrigir RLS e RPCs de perfil | P0 | 1-2 dias |
| SEC-02 | Atualizar Next.js e dependencias | P0 | 0,5-1 dia |
| AUTH-01 | Ownership por `cod_rep` | P0 | 2-4 dias |
| DATA-02 | Desativar fallback local em producao | P0 | 1-2 dias |
| FLOW-01 | Disparo de ativacao | P1 | 2-4 dias |
| FLOW-02 | Reconciliador de conversao | P1 | 3-6 dias |
| DATA-01 | Unificar fonte de pedidos | P1 | 4-8 dias |
| PRICE-01 | Sync transacional de preco | P1 | 2-4 dias |
| MSG-01 | Outbox de respostas | P1 | 3-6 dias |
| MSG-02 | Claim atomico de disparos | P1 | 1-3 dias |
| JOB-01 | Corrigir envelope do cron | P1 | 0,5 dia |
| SCHEMA-01 | Baseline completo de migrations | P1 | 3-5 dias |
| ORDER-02 | Maquina de estados | P2 | 1-2 dias |
| DATA-03 | Corrigir/remover sync de clientes | P2 | 1-3 dias |
| PRICE-02 | Validar paginacao SOAP | P2 | 1-2 dias |
| OPS-01 | CI, lint e testes de integracao | P2 | 3-6 dias |
| OPS-02 | Healthcheck e observabilidade | P2 | 3-5 dias |

## 9. Criterios de conclusao da auditoria

Esta auditoria deve ser considerada encerrada quando:

- os achados P0 forem corrigidos e testados;
- cada modulo possuir owner e fonte de verdade definida;
- o schema puder ser reconstruido do zero pelo Git;
- ativacao chegar ao WhatsApp;
- conversoes alimentarem resultados;
- nenhum representante acessar dados de outra carteira;
- falhas de banco ou envio nao gerarem confirmacoes falsas;
- CI bloquear regressao de seguranca, build e contratos.

