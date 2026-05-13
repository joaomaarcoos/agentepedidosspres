#!/usr/bin/env bash
set -euo pipefail

# ── Configurações ────────────────────────────────────────────────────────────
IMAGE="agente-pedidos"
STACK="agente-pedidos"
COMPOSE_FILE="docker-stack.yml"

# ── Helpers ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
abort()   { echo -e "${RED}[erro]${NC}  $*"; exit 1; }

# ── Pré-checks ───────────────────────────────────────────────────────────────
command -v docker &>/dev/null || abort "Docker não encontrado."
docker info &>/dev/null       || abort "Docker daemon não está rodando."

if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
  warn "Swarm não está ativo. Inicializando..."
  docker swarm init
fi

[[ -f "$COMPOSE_FILE" ]] || abort "$COMPOSE_FILE não encontrado. Execute a partir da raiz do projeto."

# ── Tag com git commit (se disponível) ───────────────────────────────────────
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
TAG="${IMAGE}:${GIT_SHA}"
LATEST="${IMAGE}:latest"

# ── Git pull (opcional, descomente se o código vem do git) ───────────────────
# info "Atualizando código..."
# git pull origin main

# ── Build ────────────────────────────────────────────────────────────────────
info "Build da imagem → $TAG"
docker build --pull -t "$TAG" -t "$LATEST" .

# ── Deploy ───────────────────────────────────────────────────────────────────
info "Deploy do stack '$STACK'..."
docker stack deploy \
  --compose-file "$COMPOSE_FILE" \
  --with-registry-auth \
  --prune \
  "$STACK"

# ── Aguarda serviço estabilizar ───────────────────────────────────────────────
info "Aguardando serviço estabilizar..."
sleep 5

REPLICAS=$(docker service ls --filter "name=${STACK}_app" --format "{{.Replicas}}" 2>/dev/null || echo "?/?")
info "Serviço: $REPLICAS réplicas ativas"

# ── Limpeza de imagens antigas ───────────────────────────────────────────────
info "Removendo imagens antigas..."
docker image prune -f --filter "label=com.docker.stack.namespace=${STACK}" 2>/dev/null || true

info "Deploy concluído. Stack: $STACK | Imagem: $TAG"
