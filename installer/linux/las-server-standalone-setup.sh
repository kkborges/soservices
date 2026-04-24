#!/usr/bin/env bash
set -euo pipefail

# LAS Server Standalone Setup (Linux, sem Docker)
# - Instala a API (uvicorn) + Celery worker + Celery beat como services (systemd)
# - Pode usar Postgres/Redis/OTel Collector existentes ou instalar localmente (opcional)
# - Usa como fonte um bundle LAS_*_DEPLOY_YYYYMMDD.tar.gz (que contem backend/ e scripts/)
#
# Exemplos:
#   sudo ./las-server-standalone-setup.sh install \
#     --bundle ./LAS_ONPREM_DEPLOY_20260424.tar.gz \
#     --install-dir /srv/las-plataforma/standalone \
#     --postgres existing --postgres-host 192.168.0.10 --postgres-user las --postgres-password '***' --postgres-db las \
#     --redis existing --redis-host 192.168.0.11 --redis-password '***' \
#     --collector existing --otel-endpoint http://192.168.0.12:4317
#
#   sudo ./las-server-standalone-setup.sh status --install-dir /srv/las-plataforma/standalone
#   sudo ./las-server-standalone-setup.sh uninstall --install-dir /srv/las-plataforma/standalone --purge

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Uso:
  $SCRIPT_NAME install   --bundle <LAS_*_DEPLOY_YYYYMMDD.tar.gz> --install-dir <dir> [opcoes]
  $SCRIPT_NAME start     --install-dir <dir>
  $SCRIPT_NAME stop      --install-dir <dir>
  $SCRIPT_NAME status    --install-dir <dir>
  $SCRIPT_NAME uninstall --install-dir <dir> [--purge]

Opcoes (install):
  --python <bin>                      (default: python3)
  --listen-host <ip>                 (default: 0.0.0.0)
  --listen-port <port>               (default: 8000)
  --env-file <path>                  (default: /etc/las/server.env)

  Postgres:
    --postgres existing|local         (default: existing)
    --postgres-host <host>
    --postgres-port <port>            (default: 5432)
    --postgres-db <db>                (default: las)
    --postgres-user <user>            (default: las)
    --postgres-password <pass>

  Redis:
    --redis existing|local            (default: existing)
    --redis-host <host>
    --redis-port <port>               (default: 6379)
    --redis-db <db>                   (default: 0)
    --redis-password <pass>

  Collector (opcional):
    --collector none|existing|local   (default: none)
    --otel-endpoint <endpoint>        (ex: http://otelcol:4317)
    --otelcol-version <ver>           (default: 0.117.0) (apenas --collector local)

Observacoes:
  - Para funcionar 100% (sinteticos/extensoes/baselines/alertas), este setup sobe 3 services:
    las-api, las-worker, las-beat.
EOF
}

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "[LAS Server] Execute como root (sudo)." >&2
    exit 2
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

detect_os_pkg_mgr() {
  if have_cmd apt-get; then echo "apt"; return 0; fi
  if have_cmd dnf; then echo "dnf"; return 0; fi
  if have_cmd yum; then echo "yum"; return 0; fi
  echo ""
}

install_pkgs() {
  local mgr="$1"; shift
  case "$mgr" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y
      apt-get install -y "$@"
      ;;
    dnf)
      dnf install -y "$@"
      ;;
    yum)
      yum install -y "$@"
      ;;
    *)
      echo "[LAS Server] Gerenciador de pacotes nao suportado. Instale manualmente: $*" >&2
      exit 2
      ;;
  esac
}

random_pw() {
  # 32 chars base64-ish
  python3 - <<'PY' 2>/dev/null || true
import secrets,string
alphabet=string.ascii_letters+string.digits
print(''.join(secrets.choice(alphabet) for _ in range(32)))
PY
}

write_env_file() {
  local env_file="$1"
  local listen_host="$2"
  local listen_port="$3"
  local pg_host="$4"
  local pg_port="$5"
  local pg_db="$6"
  local pg_user="$7"
  local pg_pass="$8"
  local redis_host="$9"
  local redis_port="${10}"
  local redis_db="${11}"
  local redis_pass="${12}"
  local otel_endpoint="${13}"

  mkdir -p "$(dirname "$env_file")"
  # Restrict permissions: secrets (db passwords) may exist here.
  umask 027
  cat >"$env_file" <<EOF
# LAS Server (standalone) - environment
# Gerado por $SCRIPT_NAME em $(date -Iseconds)

APP_HOST=${listen_host}
APP_PORT=${listen_port}
API_DOCS_ENABLED=true

POSTGRES_HOST=${pg_host}
POSTGRES_PORT=${pg_port}
POSTGRES_DB=${pg_db}
POSTGRES_USER=${pg_user}
POSTGRES_PASSWORD=${pg_pass}

REDIS_HOST=${redis_host}
REDIS_PORT=${redis_port}
REDIS_DB=${redis_db}
REDIS_PASSWORD=${redis_pass}

# Optional OTel exporter (para self-observability / exports)
OTEL_EXPORTER_OTLP_ENDPOINT=${otel_endpoint}
EOF

  chmod 640 "$env_file"
  echo "[LAS Server] Env gravado em: $env_file"
}

systemd_unit_api() {
  local install_dir="$1"
  local env_file="$2"
  local python_bin="$3"
  local unit="/etc/systemd/system/las-api.service"
  cat >"$unit" <<EOF
[Unit]
Description=LAS API (standalone)
After=network.target

[Service]
Type=simple
WorkingDirectory=${install_dir}/backend
EnvironmentFile=${env_file}
ExecStart=${python_bin} -m uvicorn app.main:app --host \${APP_HOST} --port \${APP_PORT}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
}

systemd_unit_worker() {
  local install_dir="$1"
  local env_file="$2"
  local python_bin="$3"
  local unit="/etc/systemd/system/las-worker.service"
  cat >"$unit" <<EOF
[Unit]
Description=LAS Worker (Celery)
After=network.target

[Service]
Type=simple
WorkingDirectory=${install_dir}/backend
EnvironmentFile=${env_file}
ExecStart=${python_bin} -m celery -A app.workers.celery_app.celery_app worker -l info --concurrency=2 -Q ai,synthetic,security,collector,baseline,alerts,celery
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
}

systemd_unit_beat() {
  local install_dir="$1"
  local env_file="$2"
  local python_bin="$3"
  local unit="/etc/systemd/system/las-beat.service"
  cat >"$unit" <<EOF
[Unit]
Description=LAS Beat (Celery scheduler)
After=network.target

[Service]
Type=simple
WorkingDirectory=${install_dir}/backend
EnvironmentFile=${env_file}
ExecStart=${python_bin} -m celery -A app.workers.celery_app.celery_app beat -l info
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
}

install_otelcol_local() {
  local ver="$1"
  local install_dir="$2"
  local mgr
  mgr="$(detect_os_pkg_mgr)"
  install_pkgs "$mgr" ca-certificates curl

  mkdir -p /opt/otelcol
  local url="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${ver}/otelcol-contrib_${ver}_linux_amd64.tar.gz"
  echo "[LAS Server] Baixando otelcol-contrib v${ver}..."
  curl -fsSL "$url" -o /tmp/otelcol.tgz
  tar -xzf /tmp/otelcol.tgz -C /opt/otelcol
  rm -f /tmp/otelcol.tgz

  # Minimal config: accept OTLP gRPC/HTTP locally. Receiver only.
  mkdir -p /etc/otelcol
  cat >/etc/otelcol/config.yaml <<EOF
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  debug:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      exporters: [debug]
    logs:
      receivers: [otlp]
      exporters: [debug]
EOF

  cat >/etc/systemd/system/las-otelcol.service <<EOF
[Unit]
Description=LAS OTel Collector (local)
After=network.target

[Service]
Type=simple
ExecStart=/opt/otelcol/otelcol-contrib --config /etc/otelcol/config.yaml
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable las-otelcol.service
  systemctl restart las-otelcol.service

  echo "[LAS Server] OTel Collector local ativo (4317/4318)."
  echo "[LAS Server] Obs: este collector esta em modo debug/exporter; para producao, ajuste para exportar para o LAS ou outro destino."
}

cmd="${1:-}"; shift || true

bundle=""
install_dir=""
python_bin="python3"
listen_host="0.0.0.0"
listen_port="8000"
env_file="/etc/las/server.env"

postgres_mode="existing"
postgres_host=""
postgres_port="5432"
postgres_db="las"
postgres_user="las"
postgres_password=""

redis_mode="existing"
redis_host=""
redis_port="6379"
redis_db="0"
redis_password=""

collector_mode="none"
otel_endpoint=""
otelcol_version="0.117.0"

purge=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) bundle="${2:-}"; shift 2 ;;
    --install-dir) install_dir="${2:-}"; shift 2 ;;
    --python) python_bin="${2:-}"; shift 2 ;;
    --listen-host) listen_host="${2:-}"; shift 2 ;;
    --listen-port) listen_port="${2:-}"; shift 2 ;;
    --env-file) env_file="${2:-}"; shift 2 ;;

    --postgres) postgres_mode="${2:-}"; shift 2 ;;
    --postgres-host) postgres_host="${2:-}"; shift 2 ;;
    --postgres-port) postgres_port="${2:-}"; shift 2 ;;
    --postgres-db) postgres_db="${2:-}"; shift 2 ;;
    --postgres-user) postgres_user="${2:-}"; shift 2 ;;
    --postgres-password) postgres_password="${2:-}"; shift 2 ;;

    --redis) redis_mode="${2:-}"; shift 2 ;;
    --redis-host) redis_host="${2:-}"; shift 2 ;;
    --redis-port) redis_port="${2:-}"; shift 2 ;;
    --redis-db) redis_db="${2:-}"; shift 2 ;;
    --redis-password) redis_password="${2:-}"; shift 2 ;;

    --collector) collector_mode="${2:-}"; shift 2 ;;
    --otel-endpoint) otel_endpoint="${2:-}"; shift 2 ;;
    --otelcol-version) otelcol_version="${2:-}"; shift 2 ;;

    --purge) purge=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; usage; exit 2 ;;
  esac
done

case "$cmd" in
  install|start|stop|status|uninstall) ;;
  *) usage; exit 2 ;;
esac

if [[ -z "$install_dir" ]]; then
  echo "[LAS Server] --install-dir e obrigatorio." >&2
  exit 2
fi

need_root

if [[ "$cmd" == "install" ]]; then
  if [[ -z "$bundle" ]]; then
    echo "[LAS Server] --bundle e obrigatorio no install." >&2
    exit 2
  fi
  if [[ ! -f "$bundle" ]]; then
    echo "[LAS Server] Bundle nao encontrado: $bundle" >&2
    exit 2
  fi

  if ! have_cmd systemctl; then
    echo "[LAS Server] systemd nao encontrado (systemctl). Este instalador requer systemd." >&2
    exit 2
  fi

  if ! have_cmd "$python_bin"; then
    echo "[LAS Server] Python nao encontrado: $python_bin" >&2
    exit 2
  fi

  mgr="$(detect_os_pkg_mgr)"
  if [[ -z "$mgr" ]]; then
    echo "[LAS Server] Nao foi possivel detectar gerenciador de pacotes. Instale dependencias manualmente (python3-venv, gcc, libpq-dev, etc)." >&2
    exit 2
  fi

  # Base packages for Python deps
  install_pkgs "$mgr" ca-certificates curl
  # Build deps for asyncpg
  if [[ "$mgr" == "apt" ]]; then
    install_pkgs "$mgr" python3-venv python3-pip build-essential libpq-dev
  else
    install_pkgs "$mgr" python3 python3-pip python3-virtualenv gcc postgresql-devel
  fi

  if [[ "$postgres_mode" == "local" ]]; then
    if [[ "$mgr" == "apt" ]]; then
      install_pkgs "$mgr" postgresql
    else
      install_pkgs "$mgr" postgresql-server postgresql
    fi
    systemctl enable postgresql || true
    systemctl restart postgresql || true
    postgres_host="127.0.0.1"
    postgres_password="${postgres_password:-$(random_pw)}"
    echo "[LAS Server] Configurando Postgres local (db=${postgres_db} user=${postgres_user})"
    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${postgres_user}'" | grep -q 1 || sudo -u postgres psql -c "CREATE USER ${postgres_user} WITH PASSWORD '${postgres_password}';"
    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${postgres_db}'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE ${postgres_db} OWNER ${postgres_user};"
  else
    if [[ -z "$postgres_host" ]]; then
      echo "[LAS Server] --postgres-host e obrigatorio quando --postgres existing." >&2
      exit 2
    fi
    if [[ -z "$postgres_password" ]]; then
      echo "[LAS Server] --postgres-password e obrigatorio quando --postgres existing." >&2
      exit 2
    fi
  fi

  if [[ "$redis_mode" == "local" ]]; then
    if [[ "$mgr" == "apt" ]]; then
      install_pkgs "$mgr" redis-server
    else
      install_pkgs "$mgr" redis
    fi
    systemctl enable redis || systemctl enable redis-server || true
    systemctl restart redis || systemctl restart redis-server || true
    redis_host="127.0.0.1"
    # We'll keep redis_password empty unless user sets it (avoids editing redis.conf automatically)
    redis_password="${redis_password:-}"
  else
    if [[ -z "$redis_host" ]]; then
      echo "[LAS Server] --redis-host e obrigatorio quando --redis existing." >&2
      exit 2
    fi
    # redis password can be empty depending on deployment
  fi

  if [[ "$collector_mode" == "local" ]]; then
    install_otelcol_local "$otelcol_version" "$install_dir"
    otel_endpoint="${otel_endpoint:-http://127.0.0.1:4317}"
  fi

  mkdir -p "$install_dir"
  echo "[LAS Server] Extraindo bundle para: $install_dir"
  tar -xzf "$bundle" -C "$install_dir"
  if [[ ! -d "$install_dir/backend" ]]; then
    echo "[LAS Server] Bundle extraido nao contem backend/ (esperado deploy bundle LAS_*_DEPLOY)." >&2
    exit 2
  fi

  # Venv
  if [[ ! -d "$install_dir/venv" ]]; then
    echo "[LAS Server] Criando venv..."
    "$python_bin" -m venv "$install_dir/venv"
  fi
  vpy="$install_dir/venv/bin/python"
  pip="$install_dir/venv/bin/pip"
  "$pip" install --upgrade pip wheel >/dev/null
  echo "[LAS Server] Instalando dependencias do backend..."
  "$pip" install -r "$install_dir/backend/requirements.txt"

  write_env_file "$env_file" "$listen_host" "$listen_port" "$postgres_host" "$postgres_port" "$postgres_db" "$postgres_user" "$postgres_password" "$redis_host" "$redis_port" "$redis_db" "$redis_password" "$otel_endpoint"

  echo "[LAS Server] Criando units do systemd..."
  systemd_unit_api "$install_dir" "$env_file" "$vpy"
  systemd_unit_worker "$install_dir" "$env_file" "$vpy"
  systemd_unit_beat "$install_dir" "$env_file" "$vpy"
  systemctl daemon-reload
  systemctl enable las-api.service las-worker.service las-beat.service
  systemctl restart las-api.service las-worker.service las-beat.service

  echo "[LAS Server] Instalacao concluida."
  echo "[LAS Server] API: http://${listen_host}:${listen_port}/api/health"
  exit 0
fi

if [[ "$cmd" == "start" ]]; then
  systemctl restart las-api.service las-worker.service las-beat.service
  systemctl restart las-otelcol.service >/dev/null 2>&1 || true
  exit 0
fi

if [[ "$cmd" == "stop" ]]; then
  systemctl stop las-api.service las-worker.service las-beat.service || true
  systemctl stop las-otelcol.service >/dev/null 2>&1 || true
  exit 0
fi

if [[ "$cmd" == "status" ]]; then
  systemctl --no-pager status las-api.service las-worker.service las-beat.service || true
  systemctl --no-pager status las-otelcol.service >/dev/null 2>&1 || true
  exit 0
fi

if [[ "$cmd" == "uninstall" ]]; then
  systemctl stop las-api.service las-worker.service las-beat.service || true
  systemctl disable las-api.service las-worker.service las-beat.service || true
  rm -f /etc/systemd/system/las-api.service /etc/systemd/system/las-worker.service /etc/systemd/system/las-beat.service

  systemctl stop las-otelcol.service >/dev/null 2>&1 || true
  systemctl disable las-otelcol.service >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/las-otelcol.service
  rm -rf /etc/otelcol /opt/otelcol

  systemctl daemon-reload || true
  if [[ "$purge" -eq 1 ]]; then
    rm -f "$env_file" || true
  fi
  rm -rf "$install_dir"
  echo "[LAS Server] Desinstalacao concluida."
  exit 0
fi

