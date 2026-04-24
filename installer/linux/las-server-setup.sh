#!/usr/bin/env bash
set -euo pipefail

# LAS Server Setup (Linux)
# - Instala/atualiza o "servidor principal" via Docker Compose usando um bundle LAS_*_DEPLOY_YYYYMMDD.tar.gz
# - Suporta uninstall e start/stop/status
#
# Exemplos:
#   sudo ./las-server-setup.sh install --bundle ./LAS_ONPREM_DEPLOY_20260424.tar.gz --install-dir /srv/las-plataforma/onprem
#   sudo ./las-server-setup.sh start  --install-dir /srv/las-plataforma/onprem
#   sudo ./las-server-setup.sh status --install-dir /srv/las-plataforma/onprem
#   sudo ./las-server-setup.sh uninstall --install-dir /srv/las-plataforma/onprem

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Uso:
  $SCRIPT_NAME install   --bundle <LAS_*_DEPLOY_YYYYMMDD.tar.gz> --install-dir <dir> [--mode onprem|saas] [--with-systemd]
  $SCRIPT_NAME start     --install-dir <dir> [--mode onprem|saas]
  $SCRIPT_NAME stop      --install-dir <dir> [--mode onprem|saas]
  $SCRIPT_NAME status    --install-dir <dir> [--mode onprem|saas]
  $SCRIPT_NAME uninstall --install-dir <dir> [--mode onprem|saas] [--purge-volumes]

Observacoes:
  - Requer Docker + docker-compose (ou docker compose).
  - O bundle de deploy (LAS_SAAS_DEPLOY / LAS_ONPREM_DEPLOY) contem docker-compose, scripts e docs.
EOF
}

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "[LAS Server] Execute como root (use sudo)." >&2
    exit 2
  fi
}

detect_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
      echo "docker compose"
      return 0
    fi
  fi
  echo ""
}

compose_file_for_mode() {
  local mode="$1"
  if [[ "$mode" == "saas" ]]; then
    echo "docker-compose.ha.release.yml"
  else
    echo "docker-compose.onprem-ha.release.yml"
  fi
}

compose_dir_for_install() {
  local install_dir="$1"
  echo "$install_dir/docker"
}

compose_up() {
  local mode="$1"
  local install_dir="$2"
  local dc="$3"
  local docker_dir
  docker_dir="$(compose_dir_for_install "$install_dir")"
  local f
  f="$(compose_file_for_mode "$mode")"

  if [[ ! -d "$docker_dir" ]]; then
    echo "[LAS Server] Pasta docker nao encontrada em: $docker_dir" >&2
    exit 2
  fi
  if [[ ! -f "$docker_dir/$f" ]]; then
    # fallback (dev compose)
    if [[ "$mode" == "saas" && -f "$docker_dir/docker-compose.ha.yml" ]]; then
      f="docker-compose.ha.yml"
    elif [[ "$mode" != "saas" && -f "$docker_dir/docker-compose.onprem-ha.yml" ]]; then
      f="docker-compose.onprem-ha.yml"
    else
      echo "[LAS Server] Compose file nao encontrado para mode=$mode. Esperado $docker_dir/$f" >&2
      exit 2
    fi
  fi

  pushd "$docker_dir" >/dev/null
  echo "[LAS Server] Subindo stack ($mode) usando $f"
  # shellcheck disable=SC2086
  $dc -f "$f" up -d
  popd >/dev/null
}

compose_down() {
  local mode="$1"
  local install_dir="$2"
  local dc="$3"
  local purge="${4:-0}"
  local docker_dir
  docker_dir="$(compose_dir_for_install "$install_dir")"
  local f
  f="$(compose_file_for_mode "$mode")"
  if [[ ! -f "$docker_dir/$f" ]]; then
    if [[ "$mode" == "saas" && -f "$docker_dir/docker-compose.ha.yml" ]]; then
      f="docker-compose.ha.yml"
    elif [[ "$mode" != "saas" && -f "$docker_dir/docker-compose.onprem-ha.yml" ]]; then
      f="docker-compose.onprem-ha.yml"
    fi
  fi

  if [[ ! -d "$docker_dir" ]]; then
    echo "[LAS Server] Nada para parar (docker dir inexistente)." >&2
    return 0
  fi

  pushd "$docker_dir" >/dev/null
  echo "[LAS Server] Parando stack ($mode) usando $f"
  if [[ "$purge" -eq 1 ]]; then
    # shellcheck disable=SC2086
    $dc -f "$f" down -v || true
  else
    # shellcheck disable=SC2086
    $dc -f "$f" down || true
  fi
  popd >/dev/null
}

compose_status() {
  local mode="$1"
  local install_dir="$2"
  local dc="$3"
  local docker_dir
  docker_dir="$(compose_dir_for_install "$install_dir")"
  local f
  f="$(compose_file_for_mode "$mode")"
  if [[ ! -f "$docker_dir/$f" ]]; then
    if [[ "$mode" == "saas" && -f "$docker_dir/docker-compose.ha.yml" ]]; then
      f="docker-compose.ha.yml"
    elif [[ "$mode" != "saas" && -f "$docker_dir/docker-compose.onprem-ha.yml" ]]; then
      f="docker-compose.onprem-ha.yml"
    fi
  fi

  pushd "$docker_dir" >/dev/null
  # shellcheck disable=SC2086
  $dc -f "$f" ps || true
  popd >/dev/null
}

write_systemd() {
  local mode="$1"
  local install_dir="$2"
  local dc="$3"
  local unit="/etc/systemd/system/las-server.service"
  cat >"$unit" <<EOF
[Unit]
Description=LAS Server (Docker Compose)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(compose_dir_for_install "$install_dir")
ExecStart=/usr/bin/env bash -lc '$dc -f $(compose_file_for_mode "$mode") up -d'
ExecStop=/usr/bin/env bash -lc '$dc -f $(compose_file_for_mode "$mode") down'
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable las-server.service
  echo "[LAS Server] systemd habilitado: las-server.service"
}

remove_systemd() {
  local unit="/etc/systemd/system/las-server.service"
  systemctl disable las-server.service >/dev/null 2>&1 || true
  systemctl stop las-server.service >/dev/null 2>&1 || true
  rm -f "$unit"
  systemctl daemon-reload || true
}

cmd="${1:-}"
shift || true

mode="onprem"
bundle=""
install_dir=""
with_systemd=0
purge_volumes=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) mode="${2:-}"; shift 2 ;;
    --bundle) bundle="${2:-}"; shift 2 ;;
    --install-dir) install_dir="${2:-}"; shift 2 ;;
    --with-systemd) with_systemd=1; shift ;;
    --purge-volumes) purge_volumes=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$cmd" ]]; then
  usage
  exit 2
fi

case "$cmd" in
  install|start|stop|status|uninstall) ;;
  *) echo "Comando invalido: $cmd" >&2; usage; exit 2 ;;
esac

if [[ -z "$install_dir" ]]; then
  echo "[LAS Server] --install-dir e obrigatorio." >&2
  usage
  exit 2
fi

need_root

dc="$(detect_compose)"
if [[ -z "$dc" ]]; then
  echo "[LAS Server] docker-compose nao encontrado. Instale Docker + docker-compose (ou docker compose)." >&2
  exit 2
fi

if [[ "$cmd" == "install" ]]; then
  if [[ -z "$bundle" ]]; then
    echo "[LAS Server] --bundle e obrigatorio no install." >&2
    exit 2
  fi
  if [[ ! -f "$bundle" ]]; then
    echo "[LAS Server] Bundle nao encontrado: $bundle" >&2
    exit 2
  fi

  mkdir -p "$install_dir"
  echo "[LAS Server] Extraindo bundle para: $install_dir"
  tar -xzf "$bundle" -C "$install_dir"

  # Optional: create an env file if missing (from examples in deploy bundle)
  if [[ -d "$install_dir/docker" ]]; then
    if [[ "$mode" == "onprem" && -f "$install_dir/docker/.env.onprem.example" && ! -f "$install_dir/docker/.env" ]]; then
      cp "$install_dir/docker/.env.onprem.example" "$install_dir/docker/.env"
      echo "[LAS Server] Criado $install_dir/docker/.env a partir de .env.onprem.example (ajuste conforme necessario)"
    elif [[ -f "$install_dir/docker/.env.example" && ! -f "$install_dir/docker/.env" ]]; then
      cp "$install_dir/docker/.env.example" "$install_dir/docker/.env"
      echo "[LAS Server] Criado $install_dir/docker/.env a partir de .env.example (ajuste conforme necessario)"
    fi
  fi

  compose_up "$mode" "$install_dir" "$dc"
  if [[ "$with_systemd" -eq 1 ]]; then
    write_systemd "$mode" "$install_dir" "$dc"
  fi
  echo "[LAS Server] Instalacao concluida."
  exit 0
fi

if [[ "$cmd" == "start" ]]; then
  compose_up "$mode" "$install_dir" "$dc"
  exit 0
fi

if [[ "$cmd" == "stop" ]]; then
  compose_down "$mode" "$install_dir" "$dc" 0
  exit 0
fi

if [[ "$cmd" == "status" ]]; then
  compose_status "$mode" "$install_dir" "$dc"
  exit 0
fi

if [[ "$cmd" == "uninstall" ]]; then
  compose_down "$mode" "$install_dir" "$dc" "$purge_volumes"
  remove_systemd
  echo "[LAS Server] Removendo pasta: $install_dir"
  rm -rf "$install_dir"
  echo "[LAS Server] Desinstalacao concluida."
  exit 0
fi

