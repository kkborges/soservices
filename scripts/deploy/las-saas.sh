#!/usr/bin/env bash
set -euo pipefail

# LAS SaaS / Cloud deployment helper for Docker Compose.
# This script is intentionally simple and can be copied to /srv/las-plataforma.

ROOT_DIR="${ROOT_DIR:-/srv/las-plataforma/deploy-orquestracao/docker}"
cd "$ROOT_DIR"

# Keep stable if already set by the environment; otherwise use a clear default.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-las-saas}"

HA_FILE="docker-compose.ha.images.yml"
if [ "${USE_BUILD:-0}" = "1" ]; then
  HA_FILE="docker-compose.ha.yml"
fi

FILES=(
  -f docker-compose.data-ha.yml
  -f "$HA_FILE"
  -f docker-compose.proxy-manager.yml
)

cmd="${1:-}"
shift || true

case "$cmd" in
  up)
    docker-compose "${FILES[@]}" up -d --remove-orphans
    ;;
  down)
    docker-compose "${FILES[@]}" down
    ;;
  ps)
    docker-compose "${FILES[@]}" ps
    ;;
  logs)
    docker-compose "${FILES[@]}" logs -f --tail=200 "$@"
    ;;
  restart)
    docker-compose "${FILES[@]}" restart "$@"
    ;;
  health)
    docker ps --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    ;;
  *)
    echo "Usage: $0 {up|down|ps|logs|restart|health}"
    exit 2
    ;;
esac
