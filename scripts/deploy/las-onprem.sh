#!/usr/bin/env bash
set -euo pipefail

# LAS On-Prem deployment helper for Docker Compose.
# This script is intentionally simple and can be copied to /srv/las-plataforma.

ROOT_DIR="${ROOT_DIR:-/srv/las-plataforma/deploy-onpremise/docker}"
cd "$ROOT_DIR"

# The compose file already sets `name: las-onprem`, but we keep it here for clarity.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-las-onprem}"

ONPREM_FILE="docker-compose.onprem-ha.images.yml"
if [ "${USE_BUILD:-0}" = "1" ]; then
  ONPREM_FILE="docker-compose.onprem-ha.yml"
fi

FILES=(
  -f "$ONPREM_FILE"
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
