#!/usr/bin/env bash
set -euo pipefail

# LAS Platform Universal Installer (Linux)
# Orchestrates server, agent and gateway installation from one entrypoint.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Uso:
  $SCRIPT_NAME install   --target server|agent|gateway --deployment saas|onprem --runtime compose|standalone|kubernetes [opcoes]
  $SCRIPT_NAME start     --target server --install-dir <dir> [--runtime compose|standalone] [--deployment saas|onprem]
  $SCRIPT_NAME stop      --target server --install-dir <dir> [--runtime compose|standalone] [--deployment saas|onprem]
  $SCRIPT_NAME status    --target server --install-dir <dir> [--runtime compose|standalone] [--deployment saas|onprem]
  $SCRIPT_NAME uninstall --target server|agent|gateway --install-dir <dir> [--runtime compose|standalone] [--deployment saas|onprem]

Server:
  --bundle <LAS_*_DEPLOY_YYYYMMDD.tar.gz>
  --install-dir <dir>
  --postgres existing|local --postgres-host <host> --postgres-password <pass>
  --redis existing|local --redis-host <host>
  --collector none|existing|local

Agent/Gateway via SaaS/API:
  --api-url https://api.soservices.com.br
  --username usuario@empresa.com
  --password 'senha'
  --profile infra|complete                 (agent)
  --modules infra,logs,otel,rum            (agent, opcional)
  --gateway-type agents|integrations|logs|security|control

Licenca:
  --license-file license.json              (valida modulos solicitados antes da instalacao)
  --license-key LAS...                     (gravado no install-dir/license/license.json)

Exemplos:
  sudo ./$SCRIPT_NAME install --target server --deployment onprem --runtime compose \\
    --bundle ./LAS_ONPREM_DEPLOY_20260428.tar.gz --install-dir /srv/las-plataforma/onprem

  sudo ./$SCRIPT_NAME install --target server --deployment onprem --runtime standalone \\
    --bundle ./LAS_ONPREM_DEPLOY_20260428.tar.gz --install-dir /srv/las-plataforma/standalone \\
    --postgres local --redis local --collector local

  sudo ./$SCRIPT_NAME install --target agent --api-url https://api.soservices.com.br \\
    --username demo_las@soservices.com.br --password '***' --profile complete
EOF
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

need_root_for_install() {
  local target="$1"
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "[LAS Installer] Execute como root para instalar $target (sudo)." >&2
    exit 2
  fi
}

json_array_contains() {
  local file="$1"
  local item="$2"
  python3 - "$file" "$item" <<'PY'
import json, sys
path, item = sys.argv[1], sys.argv[2]
data = json.load(open(path, encoding="utf-8"))
plan = str(data.get("plan") or "").lower()
mods = data.get("modules") or data.get("licenses") or data.get("entitlements") or []
if isinstance(mods, dict):
    mods = [k for k, v in mods.items() if v]
allowed = {str(x).lower().replace("-", "_") for x in mods}
if plan == "trial" or item in allowed or "full" in allowed:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

validate_license_modules() {
  local license_file="$1"
  local requested="$2"
  [[ -z "$license_file" || -z "$requested" ]] && return 0
  if [[ ! -f "$license_file" ]]; then
    echo "[LAS Installer] License file nao encontrado: $license_file" >&2
    exit 2
  fi
  if ! have_cmd python3; then
    echo "[LAS Installer] Python3 e necessario para validar license-file." >&2
    exit 2
  fi
  IFS=',' read -ra modules <<<"$requested"
  for module in "${modules[@]}"; do
    module="$(echo "$module" | xargs | tr '[:upper:]-' '[:lower:]_')"
    [[ -z "$module" || "$module" == "logs" ]] && continue
    if ! json_array_contains "$license_file" "$module"; then
      echo "[LAS Installer] Modulo '$module' nao esta habilitado na licenca." >&2
      exit 3
    fi
  done
}

write_license_snapshot() {
  local install_dir="$1"
  local license_file="$2"
  local license_key="$3"
  [[ -z "$install_dir" ]] && return 0
  mkdir -p "$install_dir/license"
  if [[ -n "$license_file" && -f "$license_file" ]]; then
    cp "$license_file" "$install_dir/license/license.json"
  elif [[ -n "$license_key" ]]; then
    umask 027
    cat >"$install_dir/license/license.json" <<EOF
{"license_key":"${license_key}","source":"installer","installed_at":"$(date -Iseconds)"}
EOF
  fi
}

login_cookie() {
  local api_url="$1"
  local username="$2"
  local password="$3"
  local cookie="$4"
  if [[ -z "$api_url" || -z "$username" || -z "$password" ]]; then
    echo "[LAS Installer] --api-url, --username e --password sao obrigatorios para agent/gateway." >&2
    exit 2
  fi
  curl -fsSL -c "$cookie" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${username}\",\"password\":\"${password}\"}" \
    "${api_url%/}/api/v1/auth/login" >/dev/null
}

install_remote_agent() {
  local api_url="$1" username="$2" password="$3" profile="$4" modules="$5"
  local cookie script
  cookie="$(mktemp)"
  script="$(mktemp)"
  trap 'rm -f "$cookie" "$script"' RETURN
  login_cookie "$api_url" "$username" "$password" "$cookie"
  local url="${api_url%/}/api/v1/agents/download/linux?role=agent&format=sh&profile=${profile}"
  [[ -n "$modules" ]] && url="${url}&modules=${modules}"
  echo "[LAS Installer] Baixando instalador do agente pela API..."
  curl -fsSL -b "$cookie" "$url" -o "$script"
  chmod +x "$script"
  bash "$script"
}

install_remote_gateway() {
  local api_url="$1" username="$2" password="$3" gateway_type="$4" gateway_name="$5"
  local cookie script
  cookie="$(mktemp)"
  script="$(mktemp)"
  trap 'rm -f "$cookie" "$script"' RETURN
  login_cookie "$api_url" "$username" "$password" "$cookie"
  local url="${api_url%/}/api/v1/agents/download/gateway/linux?format=sh&gateway_type=${gateway_type}"
  [[ -n "$gateway_name" ]] && url="${url}&name=${gateway_name}"
  echo "[LAS Installer] Baixando instalador do gateway pela API..."
  curl -fsSL -b "$cookie" "$url" -o "$script"
  chmod +x "$script"
  bash "$script"
}

action="${1:-}"; shift || true
target="server"
deployment="onprem"
runtime="compose"
bundle=""
install_dir=""
license_file=""
license_key=""
api_url=""
username=""
password=""
profile="infra"
modules=""
gateway_type="agents"
gateway_name=""
extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:-}"; shift 2 ;;
    --deployment) deployment="${2:-}"; shift 2 ;;
    --runtime) runtime="${2:-}"; shift 2 ;;
    --bundle) bundle="${2:-}"; extra_args+=("--bundle" "$2"); shift 2 ;;
    --install-dir) install_dir="${2:-}"; extra_args+=("--install-dir" "$2"); shift 2 ;;
    --license-file) license_file="${2:-}"; shift 2 ;;
    --license-key) license_key="${2:-}"; shift 2 ;;
    --api-url) api_url="${2:-}"; shift 2 ;;
    --username) username="${2:-}"; shift 2 ;;
    --password) password="${2:-}"; shift 2 ;;
    --profile) profile="${2:-}"; shift 2 ;;
    --modules) modules="${2:-}"; shift 2 ;;
    --gateway-type) gateway_type="${2:-}"; shift 2 ;;
    --gateway-name) gateway_name="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) extra_args+=("$1"); shift ;;
  esac
done

case "$action" in
  install|start|stop|status|uninstall) ;;
  *) usage; exit 2 ;;
esac

case "$target" in
  server|agent|gateway) ;;
  *) echo "[LAS Installer] --target invalido: $target" >&2; exit 2 ;;
esac

if [[ "$target" == "server" ]]; then
  need_root_for_install server
  [[ -n "$license_file" || -n "$license_key" ]] && write_license_snapshot "${install_dir:-/etc/las}" "$license_file" "$license_key"
  if [[ "$runtime" == "compose" ]]; then
    exec bash "$SCRIPT_DIR/las-server-setup.sh" "$action" "${extra_args[@]}" --mode "$deployment"
  elif [[ "$runtime" == "standalone" ]]; then
    exec bash "$SCRIPT_DIR/las-server-standalone-setup.sh" "$action" "${extra_args[@]}"
  elif [[ "$runtime" == "kubernetes" ]]; then
    echo "[LAS Installer] Kubernetes: aplique o pacote k8s/helm do bundle com os valores do cliente."
    echo "[LAS Installer] Comando sugerido: helm upgrade --install las-platform ./k8s/helm/las-platform -n las --create-namespace"
    exit 0
  else
    echo "[LAS Installer] --runtime invalido: $runtime" >&2
    exit 2
  fi
fi

if [[ "$target" == "agent" ]]; then
  need_root_for_install agent
  validate_license_modules "$license_file" "${modules:-$profile}"
  install_remote_agent "$api_url" "$username" "$password" "$profile" "$modules"
  exit 0
fi

if [[ "$target" == "gateway" ]]; then
  need_root_for_install gateway
  validate_license_modules "$license_file" "$gateway_type"
  install_remote_gateway "$api_url" "$username" "$password" "$gateway_type" "$gateway_name"
  exit 0
fi
