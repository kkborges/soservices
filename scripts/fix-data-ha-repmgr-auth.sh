#!/usr/bin/env bash
set -euo pipefail

# Fix repmgr auth loops on an existing Bitnami repmgr cluster.
#
# Symptom:
#   FATAL: password authentication failed for user "repmgr"
#
# Cause (common):
#   REPMGR_PASSWORD in docker/.env was rotated after the Postgres volumes were initialized,
#   so repmgrd/pgpool use a new password but the DB still has the old one.
#
# This script sets the database user's password to match the current container env.
#
# Requirements:
#   - docker running
#   - containers named `pg-0` / `pg-1` (as in docker/docker-compose.data-ha.yml)
#
# Safe for production:
#   - Does NOT delete data volumes.

PG_PRIMARY_CONTAINER="${PG_PRIMARY_CONTAINER:-pg-0}"
PG_STANDBY_CONTAINER="${PG_STANDBY_CONTAINER:-pg-1}"
PGPOOL_CONTAINER="${PGPOOL_CONTAINER:-pgpool}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker nao encontrado no PATH."
  exit 1
fi

if ! docker inspect "$PG_PRIMARY_CONTAINER" >/dev/null 2>&1; then
  echo "Container primario nao encontrado: $PG_PRIMARY_CONTAINER"
  exit 1
fi

repmgr_password="$(
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$PG_PRIMARY_CONTAINER" \
    | awk -F= '$1=="REPMGR_PASSWORD"{print $2; exit 0}'
)"

if [[ -z "${repmgr_password:-}" ]]; then
  echo "REPMGR_PASSWORD nao encontrado no env do container $PG_PRIMARY_CONTAINER."
  echo "Verifique se voce esta usando docker/docker-compose.data-ha.yml e se existe docker/.env."
  exit 1
fi

echo "Aplicando ajuste de senha do usuario repmgr no banco (sem exibir segredos)..."

# We run psql inside the container. Local socket access is used, avoiding network auth.
# Use psql variable quoting (:'var') to safely escape/quote the password.
apply_ok=""
for _i in $(seq 1 60); do
  if docker exec -i -e NEW_REPMGR_PASSWORD="$repmgr_password" "$PG_PRIMARY_CONTAINER" sh -s <<'SH'
set -e
psql -U postgres -d postgres -v ON_ERROR_STOP=1 -v new_pw="$NEW_REPMGR_PASSWORD" <<'SQL'
SELECT format('ALTER USER repmgr WITH PASSWORD %s', quote_literal(:'new_pw')) \gexec
SQL
SH
  then
    apply_ok="yes"
    break
  fi
  sleep 2
done

if [[ -z "${apply_ok:-}" ]]; then
  echo "Falha ao executar psql no container $PG_PRIMARY_CONTAINER (provavel loop de restart)."
  echo "Tente novamente apos estabilizar o container, ou desabilite temporariamente restart policy para aplicar o patch."
  exit 1
fi

echo "Reiniciando containers pg-0/pg-1 e pgpool para re-negociar replicacao..."
docker restart "$PG_PRIMARY_CONTAINER" >/dev/null
if docker inspect "$PG_STANDBY_CONTAINER" >/dev/null 2>&1; then
  docker restart "$PG_STANDBY_CONTAINER" >/dev/null
fi
if docker inspect "$PGPOOL_CONTAINER" >/dev/null 2>&1; then
  docker restart "$PGPOOL_CONTAINER" >/dev/null
fi

echo "OK. Verifique logs com:"
echo "  docker logs $PG_PRIMARY_CONTAINER --tail 100"
echo "  docker logs $PG_STANDBY_CONTAINER --tail 100"
echo "  docker logs $PGPOOL_CONTAINER --tail 100"
