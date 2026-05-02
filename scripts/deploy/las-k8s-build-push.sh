#!/usr/bin/env bash
set -euo pipefail

REGISTRY=""
TAG="4.1.0"
BACKEND_IMAGE="las-backend-release"
FRONTEND_IMAGE="las-frontend"
BACKEND_DOCKERFILE="backend/Dockerfile.release"
FRONTEND_DOCKERFILE="frontend/Dockerfile"
NO_PUSH=0

usage() {
  cat <<EOF
Uso:
  $0 --registry REGISTRY [--tag 4.1.0] [--no-push]

Exemplo:
  $0 --registry registry.soservices.com.br/las --tag 4.1.0
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry) REGISTRY="${2:-}"; shift 2 ;;
    --tag) TAG="${2:-}"; shift 2 ;;
    --backend-image) BACKEND_IMAGE="${2:-}"; shift 2 ;;
    --frontend-image) FRONTEND_IMAGE="${2:-}"; shift 2 ;;
    --backend-dockerfile) BACKEND_DOCKERFILE="${2:-}"; shift 2 ;;
    --frontend-dockerfile) FRONTEND_DOCKERFILE="${2:-}"; shift 2 ;;
    --no-push) NO_PUSH=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$REGISTRY" ]]; then
  echo "--registry e obrigatorio." >&2
  usage
  exit 2
fi

REGISTRY="${REGISTRY%/}"
BACKEND_REF="$REGISTRY/$BACKEND_IMAGE:$TAG"
FRONTEND_REF="$REGISTRY/$FRONTEND_IMAGE:$TAG"

echo "[LAS K8S] Building backend: $BACKEND_REF"
docker build -t "$BACKEND_REF" -f "$BACKEND_DOCKERFILE" backend

echo "[LAS K8S] Building frontend: $FRONTEND_REF"
docker build -t "$FRONTEND_REF" -f "$FRONTEND_DOCKERFILE" frontend

if [[ "$NO_PUSH" -eq 0 ]]; then
  echo "[LAS K8S] Pushing backend..."
  docker push "$BACKEND_REF"
  echo "[LAS K8S] Pushing frontend..."
  docker push "$FRONTEND_REF"
fi

cat <<EOF

Use no Helm:
  --set images.api.repository=$REGISTRY/$BACKEND_IMAGE \\
  --set images.api.tag=$TAG \\
  --set images.frontend.repository=$REGISTRY/$FRONTEND_IMAGE \\
  --set images.frontend.tag=$TAG
EOF
