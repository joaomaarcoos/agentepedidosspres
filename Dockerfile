# ── Stage 1: Build Next.js ─────────────────────────────────────────────────
FROM node:20-bookworm-slim AS builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

# NEXT_PUBLIC_* vars precisam estar presentes no build (são embutidas no bundle)
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production runner ─────────────────────────────────────────────
FROM node:20-bookworm-slim AS runner

# Python 3 runtime + pip + venv
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python packages em virtualenv isolado
COPY execution/requirements.txt ./execution/requirements.txt
RUN python3 -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir -r execution/requirements.txt

# Node: somente dependências de produção
COPY frontend/package*.json ./frontend/
RUN npm --prefix frontend ci --omit=dev

# Artefatos do build Next.js
COPY --from=builder /app/frontend/.next ./frontend/.next

# Scripts Python
COPY execution/ ./execution/

# Prompts da Marcela
COPY prompts/ ./prompts/

ENV NODE_ENV=production
ENV PYTHON_EXECUTABLE=/app/.venv/bin/python3

EXPOSE 3000
WORKDIR /app/frontend
CMD ["npm", "start"]
