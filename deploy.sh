#!/usr/bin/env bash
set -euo pipefail

IMAGE="agente-pedidos"
STACK="agente-pedidos"
COMPOSE_FILE="docker-stack.yml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
abort() { echo -e "${RED}[erro]${NC}  $*"; exit 1; }

command -v docker &>/dev/null || abort "Docker nao encontrado."
docker info &>/dev/null       || abort "Docker daemon nao esta rodando."

if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
  warn "Swarm nao esta ativo. Inicializando..."
  docker swarm init
fi

[[ -f "$COMPOSE_FILE" ]] || abort "$COMPOSE_FILE nao encontrado. Execute a partir da raiz do projeto."

if [[ -f ".env" ]]; then
  info "Carregando variaveis de ambiente de .env..."
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"
    key="$(printf '%s' "$key" | xargs)"

    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$key=$value"
  done < ".env"
else
  warn ".env nao encontrado; usando variaveis ja exportadas no shell."
fi

require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || abort "Variavel obrigatoria ausente: $name"
}

require_env NEXT_PUBLIC_SUPABASE_URL
require_env NEXT_PUBLIC_SUPABASE_ANON_KEY
require_env SUPABASE_URL
require_env SUPABASE_ANON_KEY

GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
TAG="${IMAGE}:${GIT_SHA}"
LATEST="${IMAGE}:latest"

# Se o codigo vem do git na VPS, descomente:
# info "Atualizando codigo..."
# git pull origin main

info "Build da imagem -> $TAG"
docker build --pull \
  --build-arg NEXT_PUBLIC_SUPABASE_URL="$NEXT_PUBLIC_SUPABASE_URL" \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY="$NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -t "$TAG" \
  -t "$LATEST" \
  .

info "Deploy do stack '$STACK'..."
docker stack deploy \
  --compose-file "$COMPOSE_FILE" \
  --with-registry-auth \
  --prune \
  "$STACK"

info "Aguardando servico estabilizar..."
sleep 5

REPLICAS=$(docker service ls --filter "name=${STACK}_agente-pedidos" --format "{{.Replicas}}" 2>/dev/null || echo "?/?")
info "Servico: $REPLICAS replicas ativas"

info "Removendo imagens antigas..."
docker image prune -f --filter "label=com.docker.stack.namespace=${STACK}" 2>/dev/null || true

info "Deploy concluido. Stack: $STACK | Imagem: $TAG"
