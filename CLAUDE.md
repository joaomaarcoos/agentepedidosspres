# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install all dependencies
npm run install:all

# Run frontend dev server (Next.js on port 3000)
npm run dev
# or directly:
cd frontend && npm run dev

# Build for production
npm run build

# Lint
npm run lint
# or:
cd frontend && npm run lint

# Run a Python script directly (JSON output to stdout)
cd execution && python recorrencia_cli.py --cod_rep 4
```

> Note: `.claude/launch.json` starts the active Next.js dev server on port 3000.

## Architecture

### Request Flow

```
Browser (React/Next.js App Router)
  -> Next.js API Routes  (frontend/app/api/**/route.ts)
  -> Server modules      (frontend/lib/server/*.ts)
  -> Python bridge       (frontend/lib/server/python.ts - child_process.spawn)
  -> Python CLI scripts  (execution/*.py - emit JSON to stdout)
  -> External services   (ClicVendas API, Supabase, OpenAI, Evolution API)
```

There is **no separate Python server** (no FastAPI/Flask running). Python scripts are spawned by Node.js, write a single JSON object to stdout, and exit. The bridge (`runPythonJson<T>`) captures that output and returns it to the API route. Default timeout is 5 minutes.

### Frontend (`frontend/`)

- **Next.js 14 App Router** with TypeScript and TailwindCSS.
- All shared TypeScript types live in [frontend/lib/types.ts](frontend/lib/types.ts).
- Client-side API calls go through [frontend/lib/api.ts](frontend/lib/api.ts).
- Server-side logic (calling Python, calling Supabase) lives in `frontend/lib/server/`.
- UI components: `frontend/components/` - `layout/` for shell (Header, Sidebar), `ui/` for reusable primitives.
- Root `app/page.tsx` redirects to `/clic-vendas`.

### Python CLI Scripts (`execution/`)

Each script is single-responsibility and deterministic:

| Script | Role |
|--------|------|
| `clic_vendas_cli.py` | Sync orders from ClicVendas |
| `clic_vendas_client.py` | HTTP client for ClicVendas auth + requests |
| `fetch_pedidos_clic.py` | Normalize raw order payloads |
| `supabase_client.py` | Persistence (Supabase or fallback to `.tmp/data/`) |
| `clientes_cli.py` | Sync clients via `/extpessoas` |
| `recorrencia_cli.py` | Compute recurrence intervals + AI validation trigger |
| `agent_validacao_recorrencia.py` | OpenAI agent - validates recurrence candidates |
| `agent_validacao_ativacao.py` | OpenAI agent - validates activation candidates |
| `disparos_recorrencia.py` | Send WhatsApp messages via Evolution API |
| `evolution_webhook.py` | Handle inbound WhatsApp webhook events |
| `conexao_cli.py` | Verify WhatsApp/Evolution API connection |

Scripts read credentials from `.env` (loaded via `python-dotenv`). Everything written under `.tmp/` is ephemeral and recreatable.

### Directives (`directives/`)

Markdown SOPs that define how each agent/flow should behave. They are **read by humans and referenced in prompts** - not loaded automatically. Add a directive here only when a new active process requires documented decision logic.

### External Services

- **ClicVendas**: Primary source for orders and clients. Auth via `CLIC_VENDAS_AUTH_URL` + credentials in `.env`. Endpoints: `/extpedidos` (orders), `/extpessoas` (clients). See `openapi-clicvendas.txt` and `REQUISICOES_CLICVENDAS.md` for full API reference.
- **Supabase** (`tsnvhhrifxcnuszzaxfk`): Primary DB. MCP server configured in `.mcp.json` using `SUPABASE_ACCESS_TOKEN` from the environment. Use MCP tools for schema inspection and SQL queries.
- **OpenAI**: Used by validation and atendimento agents. Configure with `OPENAI_API_KEY` and optional `OPENAI_MODEL`.
- **Evolution API**: WhatsApp dispatch/webhook. Configure with `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, and `EVOLUTION_INSTANCE`.

## Key Conventions

- **JSON IPC**: Python scripts must write valid JSON (and only JSON) to stdout. Anything else breaks the Node bridge.
- **Fallback storage**: `supabase_client.py` and the atendimento agent fall back to `.tmp/data/*.json` when Supabase is unreachable - useful for local dev without network.
- **Deployment**: Docker. Build command `npm --prefix frontend run build`, output `frontend/.next`.
- **No tests**: No test framework is configured. Validate behavior by running scripts directly or inspecting Supabase.
