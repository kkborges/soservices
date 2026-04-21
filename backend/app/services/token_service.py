"""
Token Service — Auto-generates tokens for agents, gateways, OTel and APM.
Called when user clicks "Download" installer — no manual token needed.
"""
import secrets
import string
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AgentToken, Gateway, Tenant
from app.core.config import settings


def _as_ini_bool(value: bool) -> str:
    return "true" if value else "false"


def _normalize_modules(modules: Optional[list]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for module in modules or ["infra", "processes", "services", "logs"]:
        item = str(module).strip().lower().replace("-", "_")
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    if "logs" not in seen:
        normalized.append("logs")
    return normalized


def _agent_features(modules: Optional[list]) -> tuple[list[str], dict[str, bool]]:
    normalized = _normalize_modules(modules)
    module_set = set(normalized)
    features = {
        "process_monitor": "processes" in module_set or "infra" in module_set,
        "service_monitor": "services" in module_set,
        "port_scan": "infra" in module_set,
        "disk_monitor": "infra" in module_set,
        "network_monitor": "infra" in module_set,
        "log_collection": True,
        "otel_enabled": "otel" in module_set or "traces" in module_set,
        "traces_enabled": "traces" in module_set,
        "rum_enabled": "rum" in module_set,
        "ids_enabled": "ids" in module_set,
        "vuln_scan_enabled": "vuln_scan" in module_set,
        "apm_enabled": "otel" in module_set or "traces" in module_set,
    }
    return normalized, features


def _gateway_features(gateway_config: Optional[dict]) -> dict[str, bool]:
    modules = (gateway_config or {}).get("modules") or {}
    if not modules:
        modules = {
            "agent_proxy": True,
            "logs": True,
            "otel": True,
            "traces": True,
            "rum": True,
            "integrations": False,
            "database": False,
            "messaging": False,
            "itsm": False,
            "webhooks": False,
            "security": False,
            "ids": False,
            "pentest": False,
            "network_discovery": False,
            "snmp": False,
            "syslog": False,
        }
    return {key: bool(value) for key, value in modules.items()}


def _generate_token(prefix: str, length: int = 48) -> str:
    """Generate a secure token with prefix: nxa_<random> or nxg_<random>"""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{random_part}"


async def create_agent_token(
    db: AsyncSession,
    tenant_id: str,
    role: str = "agent",
    name: Optional[str] = None,
    description: Optional[str] = None,
    expires_days: Optional[int] = None,
    install_config: Optional[dict] = None,
) -> AgentToken:
    """
    Auto-create and persist an agent token.
    Called on-demand when downloading an installer script.
    """
    token_str = _generate_token(settings.AGENT_TOKEN_PREFIX)

    expires_at = None
    if expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    token = AgentToken(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        token=token_str,
        name=name or f"Agent Token {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        description=description or f"Auto-generated on download ({role})",
        role=role,
        active=True,
        expires_at=expires_at,
        install_config=install_config or {},
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def create_gateway_token(
    db: AsyncSession,
    tenant_id: str,
    name: str,
    gateway_type: str = "infra",
    host: str = "0.0.0.0",
    port: int = 8080,
    config: Optional[dict] = None,
    reuse_pending: bool = False,
) -> Gateway:
    """
    Auto-create a gateway with a fresh token.
    """
    token_str = _generate_token(settings.GATEWAY_TOKEN_PREFIX)

    merged_config = {
        "priority": 100,
        "weight": 1,
        "cluster_name": "default",
        "failover_only": False,
        "shared_with_tenants": False,
        "heartbeat_interval": 60,
        "task_poll_interval": 20,
        "modules": {
            "logs": True,
            "otel": True,
            "security": True,
            "ids": True,
            "network_discovery": True,
            "snmp": True,
            "syslog": True,
        },
        "syslog": {
            "enabled": True,
            "listen_host": "0.0.0.0",
            "udp_port": 514,
            "tcp_port": 514,
            "tls_port": 6514,
        },
        "transport": {
            "mtls_required": True,
            "compress_enabled": True,
            "encrypt_enabled": True,
        },
        **(config or {}),
    }

    if reuse_pending:
        result = await db.execute(
            select(Gateway)
            .where(
                Gateway.tenant_id == tenant_id,
                Gateway.type == gateway_type,
                Gateway.status == "pending_install",
                Gateway.last_heartbeat.is_(None),
            )
        )
        for candidate in result.scalars().all():
            candidate_config = candidate.config or {}
            if candidate_config.get("provisioning_source") != merged_config.get("provisioning_source"):
                continue
            if candidate_config.get("installer_os") != merged_config.get("installer_os"):
                continue
            candidate.name = name
            candidate.host = host
            candidate.port = port
            candidate.config = {**candidate_config, **merged_config}
            candidate.tls_enabled = True
            candidate.compress_enabled = True
            candidate.encrypt_enabled = True
            await db.commit()
            await db.refresh(candidate)
            return candidate

    gateway = Gateway(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        type=gateway_type,
        host=host,
        port=port,
        token=token_str,
        status="pending_install",
        tls_enabled=True,
        compress_enabled=True,
        encrypt_enabled=True,
        config=merged_config,
    )
    db.add(gateway)
    await db.commit()
    await db.refresh(gateway)
    return gateway


async def get_or_create_otel_token(
    db: AsyncSession,
    tenant_id: str,
    service_name: Optional[str] = None,
) -> AgentToken:
    """
    Get existing OTel token for tenant or create one automatically.
    """
    from sqlalchemy import select

    existing = await db.execute(
        select(AgentToken).where(
            AgentToken.tenant_id == tenant_id,
            AgentToken.role == "otel",
            AgentToken.active == True,
        )
    )
    token = existing.scalar_one_or_none()

    if not token:
        token = await create_agent_token(
            db=db,
            tenant_id=tenant_id,
            role="otel",
            name=f"OTel Token — {service_name or 'default'}",
            description="Auto-generated OTel/APM token",
        )

    return token


def build_linux_install_script(
    platform_url: str,
    token: str,
    role: str = "agent",
    modules: list = None,
) -> str:
    """Generate the Linux bash installer with embedded token."""
    modules_str = ",".join(modules or ["infra", "logs", "otel"])
    return f"""#!/bin/bash
# ============================================================
# Nexus Platform Agent Installer v4.0
# Auto-generated — token embedded, no manual configuration needed
# ============================================================

set -e

NEXUS_URL="{platform_url}"
NEXUS_TOKEN="{token}"
NEXUS_ROLE="{role}"
NEXUS_MODULES="{modules_str}"
NEXUS_VERSION="4.0.0"
INSTALL_DIR="/opt/las"
SERVICE_NAME="las-agent"
LOG_DIR="/var/log/las"
CONFIG_DIR="/etc/las"
MTLS_PLATFORM_URL="{settings.MTLS_PLATFORM_URL}"

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

echo -e "${{BLUE}}"
echo "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo "  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║"
echo "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo -e "${{NC}}"
echo -e "${{GREEN}}Nexus Platform v4.0 — Instalação do Agente${{NC}}"
echo ""

# Check root
if [[ $EUID -ne 0 ]]; then
   echo -e "${{RED}}ERRO: Execute como root (sudo bash install.sh)${{NC}}"
   exit 1
fi

detect_os() {{
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        echo -e "${{RED}}Sistema operacional não suportado${{NC}}"
        exit 1
    fi
    echo -e "Sistema detectado: ${{GREEN}}$OS $OS_VERSION${{NC}}"
}}

install_dependencies() {{
    echo -e "${{YELLOW}}Instalando dependências...${{NC}}"
    case $OS in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq python3 python3-pip curl wget ca-certificates systemd net-tools
            ;;
        centos|rhel|fedora|rocky|almalinux)
            yum install -y python3 python3-pip curl wget ca-certificates net-tools 2>/dev/null || \
            dnf install -y python3 python3-pip curl wget ca-certificates net-tools
            ;;
        alpine)
            apk add --no-cache python3 py3-pip curl wget ca-certificates
            ;;
    esac
}}

create_directories() {{
    mkdir -p $INSTALL_DIR $LOG_DIR $CONFIG_DIR
    chmod 750 $CONFIG_DIR $INSTALL_DIR
    chmod 755 $LOG_DIR
}}

write_config() {{
    cat > $CONFIG_DIR/las.conf << 'CONF'
[las]
platform_url = {platform_url}
agent_token = {token}
role = {role}
modules = {modules_str}
log_dir = /var/log/las
install_dir = /opt/las

[intervals]
heartbeat_interval = 60
metrics_interval = 30
log_batch_interval = 30
ids_scan_interval = 60

[features]
process_monitor = true
port_scan = true
disk_monitor = true
network_monitor = true
log_collection = true
otel_enabled = false
ids_enabled = false
apm_enabled = false

[log_paths]
paths = /var/log/syslog,/var/log/auth.log,/var/log/nginx/*.log,/var/log/apache2/*.log

[security]
tls_verify = true
compress_data = true
encrypt_data = true
CONF
    chmod 600 $CONFIG_DIR/las.conf
}}

download_agent() {{
    echo -e "${{YELLOW}}Baixando agente...${{NC}}"
    curl -fsSL "$NEXUS_URL/api/v1/agents/artifacts/linux-agent.py" \
        -H "Authorization: Bearer $NEXUS_TOKEN" \
        -o $INSTALL_DIR/las-agent.py
    chmod +x $INSTALL_DIR/las-agent.py
}}

install_pip_deps() {{
    echo -e "${{YELLOW}}Instalando dependências Python...${{NC}}"
    pip3 install -q psutil requests cryptography 2>/dev/null || true
}}

install_service() {{
    cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=LAS Agent v4.0
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=root
ExecStart=/usr/bin/python3 $INSTALL_DIR/las-agent.py
StandardOutput=append:$LOG_DIR/agent.log
StandardError=append:$LOG_DIR/agent-error.log
Environment=LAS_CONFIG=$CONFIG_DIR/las.conf
Environment=NEXUS_CONFIG=$CONFIG_DIR/las.conf

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl start $SERVICE_NAME
    sleep 2
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${{GREEN}}✅ Agente instalado e rodando!${{NC}}"
    else
        echo -e "${{RED}}❌ Falha ao iniciar o agente. Verifique os logs: journalctl -u $SERVICE_NAME${{NC}}"
        exit 1
    fi
}}

verify_connection() {{
    echo -e "${{YELLOW}}Verificando conexão com a plataforma...${{NC}}"
    RESPONSE=$(curl -s -o /dev/null -w "%{{http_code}}" \
        "$NEXUS_URL/api/v1/ingest/agent/ping" \
        -H "Authorization: Bearer $NEXUS_TOKEN")
    
    if [ "$RESPONSE" = "200" ]; then
        echo -e "${{GREEN}}✅ Conexão com a plataforma estabelecida!${{NC}}"
    else
        echo -e "${{YELLOW}}⚠️  Não foi possível verificar conexão (HTTP $RESPONSE). O agente tentará novamente.${{NC}}"
    fi
}}

# Main installation
detect_os
install_dependencies
create_directories
write_config
install_pip_deps
download_agent
install_service
verify_connection

echo ""
echo -e "${{GREEN}}============================================${{NC}}"
echo -e "${{GREEN}}✅ Nexus Agent instalado com sucesso!${{NC}}"
echo -e "${{GREEN}}============================================${{NC}}"
echo ""
echo "  Token: ${{YELLOW}}{token}${{NC}}"
echo "  Plataforma: ${{BLUE}}{platform_url}${{NC}}"
echo "  Logs: ${{BLUE}}journalctl -u $SERVICE_NAME -f${{NC}}"
echo ""
"""


def build_docker_compose(
    platform_url: str,
    token: str,
    role: str = "agent",
    modules: list = None,
    gateway_urls: Optional[list[str]] = None,
) -> str:
    modules, features = _agent_features(modules)
    modules_str = ",".join(modules)
    gateway_urls_str = ",".join(gateway_urls or [])
    return f"""version: '3.8'
services:
  las-agent:
    image: python:3.12-slim
    container_name: las-agent
    restart: unless-stopped
    environment:
      DEBIAN_FRONTEND: "noninteractive"
      PIP_ROOT_USER_ACTION: "ignore"
      NEXUS_URL: "{platform_url}"
      MTLS_PLATFORM_URL: "{settings.MTLS_PLATFORM_URL}"
      NEXUS_TOKEN: "{token}"
      NEXUS_ROLE: "{role}"
      NEXUS_MODULES: "{modules_str}"
      LAS_CONFIG: "/etc/las/agent.conf"
      NEXUS_CONFIG: "/etc/las/agent.conf"
    volumes:
      - las-agent-data:/opt/las
      - las-agent-config:/etc/las
      - /var/log:/host/var/log:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /etc:/host/etc:ro
    network_mode: host
    privileged: true
    command: |
      sh -lc 'set -eu
      export DEBIAN_FRONTEND=noninteractive
      export PIP_ROOT_USER_ACTION=ignore
      echo "[LAS Agent] Preparando dependencias em modo noninteractive..."
      apt-get update -qq -o=Dpkg::Use-Pty=0
      apt-get install -y -qq -o=Dpkg::Use-Pty=0 --no-install-recommends curl ca-certificates >/dev/null
      python -m pip install --disable-pip-version-check --no-cache-dir -q psutil
      echo "[LAS Agent] Gerando configuracao e certificados mTLS..."
      mkdir -p /opt/las /etc/las /var/log/las
      printf "%s\\n" \
        "[las]" \
        "platform_url = {platform_url}" \
        "agent_token = {token}" \
        "role = {role}" \
        "modules = {modules_str}" \
        "log_dir = /var/log/las" \
        "install_dir = /opt/las" \
        "" \
        "[intervals]" \
        "heartbeat_interval = 60" \
        "metrics_interval = 30" \
        "" \
        "[routing]" \
        "gateway_urls = {gateway_urls_str}" \
        "routing_refresh_interval = 300" \
        "gateway_strategy = priority-weighted-failover" \
        "" \
        "[mtls]" \
        "enabled = true" \
        "required = true" \
        "platform_url = __MTLS_PLATFORM_URL__" \
        "ca_file = /etc/las/mtls-ca.pem" \
        "client_cert_file = /etc/las/mtls-client.pem" \
        "client_key_file = /etc/las/mtls-client-key.pem" \
        "" \
        "[transport]" \
        "compress_data = true" \
        "protect_data = true" \
        "protection = mtls" \
        "" \
        "[features]" \
        "process_monitor = {_as_ini_bool(features["process_monitor"])}" \
        "service_monitor = {_as_ini_bool(features["service_monitor"])}" \
        "port_scan = {_as_ini_bool(features["port_scan"])}" \
        "disk_monitor = {_as_ini_bool(features["disk_monitor"])}" \
        "network_monitor = {_as_ini_bool(features["network_monitor"])}" \
        "log_collection = {_as_ini_bool(features["log_collection"])}" \
        "otel_enabled = {_as_ini_bool(features["otel_enabled"])}" \
        "traces_enabled = {_as_ini_bool(features["traces_enabled"])}" \
        "rum_enabled = {_as_ini_bool(features["rum_enabled"])}" \
        "ids_enabled = {_as_ini_bool(features["ids_enabled"])}" \
        "vuln_scan_enabled = {_as_ini_bool(features["vuln_scan_enabled"])}" \
        "apm_enabled = {_as_ini_bool(features["apm_enabled"])}" \
        "" \
        "[log_paths]" \
        "paths = /host/var/log/syslog,/host/var/log/auth.log,/host/var/log/nginx/*.log,/host/var/log/apache2/*.log" \
        > /etc/las/agent.conf
      # Bootstrap mTLS bundle via the public Platform URL (regular TLS). The CA obtained here is then used for the mTLS edge.
      MTLS_JSON=$$(curl -fsSL "{platform_url}/api/v1/agents/bootstrap/mtls?hostname=$$(hostname)" -H "Authorization: Bearer {token}")
      export MTLS_JSON
      python -c "import json, os; from pathlib import Path; p=json.loads(os.environ['MTLS_JSON']); b=Path('/etc/las'); (b/'mtls-ca.pem').write_text(p['ca_pem'], encoding='ascii'); (b/'mtls-client.pem').write_text(p['client_cert_pem'], encoding='ascii'); (b/'mtls-client-key.pem').write_text(p['client_key_pem'], encoding='ascii'); mtls=p.get('mtls_platform_url') or '{settings.MTLS_PLATFORM_URL}'; conf=(b/'agent.conf'); conf.write_text(conf.read_text(encoding='utf-8').replace('__MTLS_PLATFORM_URL__', mtls), encoding='utf-8')"
      MTLS_PLATFORM_URL=$$(python -c "import json, os; print(json.loads(os.environ['MTLS_JSON']).get('mtls_platform_url') or '')")
      if [ -z "$$MTLS_PLATFORM_URL" ]; then MTLS_PLATFORM_URL="{settings.MTLS_PLATFORM_URL}"; fi
      echo "[LAS Agent] Baixando agente atualizado..."
      GW_URLS="{gateway_urls_str}"
      DOWNLOADED="0"
      if [ -n "$$GW_URLS" ]; then
        OLDIFS="$$IFS"; IFS=','
        for gw in $$GW_URLS; do
          IFS="$$OLDIFS"
          gw="$$(printf "%s" "$$gw" | sed "s/[[:space:]]//g" | sed "s#/*$##")"
          if [ -z "$$gw" ]; then IFS=','; continue; fi
          echo "[LAS Agent] Tentando baixar via gateway $$gw ..."
          if curl -fL --retry 2 --retry-connrefused --connect-timeout 8 --max-time 60 --progress-bar \
            --cacert /etc/las/mtls-ca.pem \
            --cert /etc/las/mtls-client.pem \
            --key /etc/las/mtls-client-key.pem \
            "$$gw/api/v1/agents/artifacts/linux-agent.py" \
            -o /opt/las/las-agent.py ; then
            DOWNLOADED="1"
            break
          fi
          IFS=','
        done
        IFS="$$OLDIFS"
      fi
      if [ "$$DOWNLOADED" != "1" ]; then
        echo "[LAS Agent] Baixando via SaaS (mTLS edge) $$MTLS_PLATFORM_URL ..."
        curl -fL --retry 3 --retry-connrefused --progress-bar \
          --cacert /etc/las/mtls-ca.pem \
          --cert /etc/las/mtls-client.pem \
          --key /etc/las/mtls-client-key.pem \
          "$$MTLS_PLATFORM_URL/api/v1/agents/artifacts/linux-agent.py" \
          -H "Authorization: Bearer {token}" \
          -o /opt/las/las-agent.py
      fi
      echo "[LAS Agent] Iniciando coleta real de infra/logs/processos..."
      exec python /opt/las/las-agent.py'
    labels:
      - "com.nexus.managed=true"
volumes:
  las-agent-data:
  las-agent-config:
"""


def build_k8s_manifest(
    platform_url: str,
    token: str,
    role: str = "k8s",
    modules: list = None,
    gateway_urls: Optional[list[str]] = None,
) -> str:
    modules, features = _agent_features(modules)
    modules_str = ",".join(modules)
    gateway_urls_str = ",".join(gateway_urls or [])
    return f"""apiVersion: v1
kind: Namespace
metadata:
  name: las-monitoring
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: las-agent
  namespace: las-monitoring
  labels:
    app: las-agent
spec:
  selector:
    matchLabels:
      app: las-agent
  template:
    metadata:
      labels:
        app: las-agent
    spec:
      hostNetwork: true
      hostPID: true
      tolerations:
        - key: node-role.kubernetes.io/master
          effect: NoSchedule
        - key: node-role.kubernetes.io/control-plane
          effect: NoSchedule
      containers:
        - name: las-agent
          image: python:3.12-slim
          imagePullPolicy: IfNotPresent
          env:
            - name: NEXUS_URL
              value: "{platform_url}"
            - name: MTLS_PLATFORM_URL
              value: "{settings.MTLS_PLATFORM_URL}"
            - name: NEXUS_TOKEN
              value: "{token}"
            - name: NEXUS_ROLE
              value: "{role}"
            - name: NEXUS_MODULES
              value: "{modules_str}"
            - name: LAS_CONFIG
              value: "/etc/las/agent.conf"
            - name: NEXUS_CONFIG
              value: "/etc/las/agent.conf"
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
          volumeMounts:
            - name: proc
              mountPath: /host/proc
              readOnly: true
            - name: sys
              mountPath: /host/sys
              readOnly: true
            - name: varlog
              mountPath: /host/var/log
              readOnly: true
            - name: las-config
              mountPath: /etc/las
            - name: las-data
              mountPath: /opt/las
          securityContext:
            privileged: true
          command: ["/bin/sh", "-lc"]
          args:
            - |
              set -eu
              export DEBIAN_FRONTEND=noninteractive
              export PIP_ROOT_USER_ACTION=ignore
              apt-get update -qq -o=Dpkg::Use-Pty=0
              apt-get install -y -qq -o=Dpkg::Use-Pty=0 --no-install-recommends curl ca-certificates >/dev/null
              python -m pip install --disable-pip-version-check --no-cache-dir -q psutil
              mkdir -p /opt/las /etc/las /var/log/las
              printf "%s\\n" \
                "[las]" \
                "platform_url = {platform_url}" \
                "agent_token = {token}" \
                "role = {role}" \
                "modules = {modules_str}" \
                "log_dir = /var/log/las" \
                "install_dir = /opt/las" \
                "" \
                "[intervals]" \
                "heartbeat_interval = 60" \
                "metrics_interval = 30" \
                "" \
                "[routing]" \
                "gateway_urls = {gateway_urls_str}" \
                "routing_refresh_interval = 300" \
                "gateway_strategy = priority-weighted-failover" \
                "" \
                "[mtls]" \
                "enabled = true" \
                "required = true" \
                "platform_url = __MTLS_PLATFORM_URL__" \
                "ca_file = /etc/las/mtls-ca.pem" \
                "client_cert_file = /etc/las/mtls-client.pem" \
                "client_key_file = /etc/las/mtls-client-key.pem" \
                "" \
                "[transport]" \
                "compress_data = true" \
                "protect_data = true" \
                "protection = mtls" \
                "" \
                "[features]" \
                "process_monitor = {_as_ini_bool(features["process_monitor"])}" \
                "service_monitor = {_as_ini_bool(features["service_monitor"])}" \
                "port_scan = {_as_ini_bool(features["port_scan"])}" \
                "disk_monitor = {_as_ini_bool(features["disk_monitor"])}" \
                "network_monitor = {_as_ini_bool(features["network_monitor"])}" \
                "log_collection = {_as_ini_bool(features["log_collection"])}" \
                "otel_enabled = {_as_ini_bool(features["otel_enabled"])}" \
                "traces_enabled = {_as_ini_bool(features["traces_enabled"])}" \
                "rum_enabled = {_as_ini_bool(features["rum_enabled"])}" \
                "ids_enabled = {_as_ini_bool(features["ids_enabled"])}" \
                "vuln_scan_enabled = {_as_ini_bool(features["vuln_scan_enabled"])}" \
                "apm_enabled = {_as_ini_bool(features["apm_enabled"])}" \
                "" \
                "[log_paths]" \
                "paths = /host/var/log/syslog,/host/var/log/auth.log,/host/var/log/nginx/*.log,/host/var/log/apache2/*.log" \
                > /etc/las/agent.conf
              MTLS_JSON=$(curl -fsSL "{platform_url}/api/v1/agents/bootstrap/mtls?hostname=$(hostname)" -H "Authorization: Bearer {token}")
              export MTLS_JSON
              python -c "import json, os; from pathlib import Path; p=json.loads(os.environ['MTLS_JSON']); b=Path('/etc/las'); (b/'mtls-ca.pem').write_text(p['ca_pem'], encoding='ascii'); (b/'mtls-client.pem').write_text(p['client_cert_pem'], encoding='ascii'); (b/'mtls-client-key.pem').write_text(p['client_key_pem'], encoding='ascii'); mtls=p.get('mtls_platform_url') or '{settings.MTLS_PLATFORM_URL}'; conf=(b/'agent.conf'); conf.write_text(conf.read_text(encoding='utf-8').replace('__MTLS_PLATFORM_URL__', mtls), encoding='utf-8')"
              MTLS_PLATFORM_URL=$(python -c "import json, os; print(json.loads(os.environ['MTLS_JSON']).get('mtls_platform_url') or '')")
              if [ -z \"$MTLS_PLATFORM_URL\" ]; then MTLS_PLATFORM_URL=\"{settings.MTLS_PLATFORM_URL}\"; fi
              GW_URLS="{gateway_urls_str}"
              DOWNLOADED="0"
              if [ -n \"$GW_URLS\" ]; then
                OLDIFS=\"$IFS\"; IFS=','
                for gw in $GW_URLS; do
                  IFS=\"$OLDIFS\"
                  gw=$(printf \"%s\" \"$gw\" | sed \"s/[[:space:]]//g\" | sed \"s#/*$##\")
                  if [ -z \"$gw\" ]; then IFS=','; continue; fi
                  echo \"[LAS Agent] Tentando baixar via gateway $gw ...\"
                  if curl -fL --retry 2 --retry-connrefused --connect-timeout 8 --max-time 60 --progress-bar \
                    --cacert /etc/las/mtls-ca.pem \
                    --cert /etc/las/mtls-client.pem \
                    --key /etc/las/mtls-client-key.pem \
                    \"$gw/api/v1/agents/artifacts/linux-agent.py\" \
                    -o /opt/las/las-agent.py ; then
                    DOWNLOADED=\"1\"
                    break
                  fi
                  IFS=','
                done
                IFS=\"$OLDIFS\"
              fi
              if [ \"$DOWNLOADED\" != \"1\" ]; then
                echo \"[LAS Agent] Baixando via SaaS (mTLS edge) $MTLS_PLATFORM_URL ...\"
                curl -fL --retry 3 --retry-connrefused --progress-bar \
                  --cacert /etc/las/mtls-ca.pem \
                  --cert /etc/las/mtls-client.pem \
                  --key /etc/las/mtls-client-key.pem \
                  \"$MTLS_PLATFORM_URL/api/v1/agents/artifacts/linux-agent.py\" \
                  -H \"Authorization: Bearer {token}\" \
                  -o /opt/las/las-agent.py
              fi
              exec python /opt/las/las-agent.py
      volumes:
        - name: proc
          hostPath:
            path: /proc
        - name: sys
          hostPath:
            path: /sys
        - name: varlog
          hostPath:
            path: /var/log
        - name: las-config
          emptyDir: {{}}
        - name: las-data
          emptyDir: {{}}
"""


def build_gateway_install_script(
    platform_url: str,
    token: str,
    gateway_type: str = "agents",
    gateway_config: Optional[dict] = None,
) -> str:
    """Generate a Linux gateway installer with embedded token."""
    features = _gateway_features(gateway_config)
    syslog_config = (gateway_config or {}).get("syslog") or {}
    syslog_enabled = bool(syslog_config.get("enabled", features.get("syslog", False)))
    syslog_host = syslog_config.get("listen_host", "0.0.0.0")
    syslog_udp_port = int(syslog_config.get("udp_port", 514))
    syslog_tcp_port = int(syslog_config.get("tcp_port", 514))
    syslog_tls_port = int(syslog_config.get("tls_port", 6514))
    return f"""#!/bin/bash
set -e

NEXUS_URL="{platform_url}"
NEXUS_TOKEN="{token}"
GATEWAY_TYPE="{gateway_type}"
INSTALL_DIR="/opt/las-gateway"
CONFIG_DIR="/etc/las"
SERVICE_NAME="las-gateway"

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"

if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq python3 curl
fi

curl -fsSL "$NEXUS_URL/api/v1/agents/artifacts/gateway.py" \\
  -H "Authorization: Bearer $NEXUS_TOKEN" \\
  -o "$INSTALL_DIR/las-gateway.py"
chmod +x "$INSTALL_DIR/las-gateway.py"

cat > "$CONFIG_DIR/gateway.conf" <<CONF
[las]
platform_url = {platform_url}
gateway_token = {token}
type = {gateway_type}
listen_port = 8080

[intervals]
heartbeat_interval = 60
CONF

cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=LAS Gateway
After=network.target

[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/python3 $INSTALL_DIR/las-gateway.py
Environment=LAS_CONFIG=$CONFIG_DIR/gateway.conf
Environment=NEXUS_CONFIG=$CONFIG_DIR/gateway.conf

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME
echo "Gateway instalado. Status: systemctl status $SERVICE_NAME"
"""


def build_windows_gateway_install_script(platform_url: str, token: str, gateway_type: str = "infra") -> str:
    """Generate a Windows PowerShell gateway installer with embedded token."""
    return f"""# ============================================================
# LAS Plataforma de Monitoramento e Observabilidade
# Instalador do Gateway LAS v4.0 - Windows PowerShell
# ============================================================

$ErrorActionPreference = "Stop"

$NEXUS_URL = "{platform_url}"
$NEXUS_TOKEN = "{token}"
$GATEWAY_TYPE = "{gateway_type}"
$INSTALL_DIR = "C:\\LASGateway"
$CONFIG_DIR = "C:\\LASGateway\\config"
$LOG_DIR = "C:\\LASGateway\\logs"
$SERVICE_NAME = "LASGateway"

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

@"
[las]
platform_url = {platform_url}
gateway_token = {token}
type = {gateway_type}
listen_host = 0.0.0.0
listen_port = 8080

[intervals]
heartbeat_interval = 60
"@ | Set-Content "$CONFIG_DIR\\gateway.conf" -Encoding UTF8

$headers = @{{ "Authorization" = "Bearer $NEXUS_TOKEN" }}
Invoke-WebRequest -Uri "$NEXUS_URL/api/v1/agents/artifacts/gateway.py" `
  -Headers $headers `
  -OutFile "$INSTALL_DIR\\las-gateway.py"

$pythonPath = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $pythonPath) {{
    Write-Host "Python não encontrado. Instale Python 3.12 antes de continuar." -ForegroundColor Red
    exit 1
}}

& pip install requests -q

$nssmPath = "$INSTALL_DIR\\nssm.exe"
if (-not (Test-Path $nssmPath)) {{
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\\nssm.zip"
    Expand-Archive -Path "$env:TEMP\\nssm.zip" -DestinationPath "$env:TEMP\\nssm" -Force
    Copy-Item "$env:TEMP\\nssm\\nssm-2.24\\win64\\nssm.exe" $nssmPath -Force
}}

& $nssmPath install $SERVICE_NAME $pythonPath "$INSTALL_DIR\\las-gateway.py"
& $nssmPath set $SERVICE_NAME AppParameters "$INSTALL_DIR\\las-gateway.py"
& $nssmPath set $SERVICE_NAME AppDirectory $INSTALL_DIR
& $nssmPath set $SERVICE_NAME AppStdout "$LOG_DIR\\gateway.log"
& $nssmPath set $SERVICE_NAME AppStderr "$LOG_DIR\\gateway-error.log"
& $nssmPath set $SERVICE_NAME Start SERVICE_AUTO_START
& $nssmPath set $SERVICE_NAME AppEnvironmentExtra \"LAS_CONFIG=$CONFIG_DIR\\gateway.conf`nNEXUS_CONFIG=$CONFIG_DIR\\gateway.conf\"

Start-Service $SERVICE_NAME
Write-Host "Gateway LAS instalado. Verifique com Get-Service $SERVICE_NAME" -ForegroundColor Green
"""


def build_linux_install_script(
    platform_url: str,
    token: str,
    role: str = "agent",
    modules: list = None,
    gateway_urls: Optional[list[str]] = None,
) -> str:
    """Generate the Linux bash installer with embedded token."""
    modules, features = _agent_features(modules)
    modules_str = ",".join(modules)
    gateway_urls_str = ",".join(gateway_urls or [])
    return f"""#!/bin/bash
set -e

PLATFORM_URL="{platform_url}"
AGENT_TOKEN="{token}"
AGENT_ROLE="{role}"
AGENT_MODULES="{modules_str}"
GATEWAY_URLS="{gateway_urls_str}"
INSTALL_DIR="/opt/las"
SERVICE_NAME="las-agent"
LOG_DIR="/var/log/las"
CONFIG_DIR="/etc/las"

RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

echo -e "${{BLUE}}LAS Plataforma de Monitoramento e Observabilidade${{NC}}"
echo -e "${{GREEN}}Instalacao do agente Linux${{NC}}"

if [[ $EUID -ne 0 ]]; then
    echo -e "${{RED}}Execute como root: sudo bash install.sh${{NC}}"
    exit 1
fi

uninstall_agent() {{
    echo -e "${{YELLOW}}Desinstalando agente Linux...${{NC}}"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    fi
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl daemon-reload 2>/dev/null || true
        systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true
    fi
    rm -rf "$INSTALL_DIR"
    if [ "${{2:-}}" = "--purge" ] || [ "${{1:-}}" = "--purge" ]; then
        rm -f "$CONFIG_DIR/agent.conf"
        echo -e "${{YELLOW}}Configuracao do agente removida. Logs preservados em $LOG_DIR.${{NC}}"
    else
        echo -e "${{YELLOW}}Configuracao preservada em $CONFIG_DIR/agent.conf. Use --purge para remover.${{NC}}"
    fi
    echo -e "${{GREEN}}Agente Linux desinstalado.${{NC}}"
}}

case "${{1:-}}" in
    --uninstall|uninstall|remove)
        uninstall_agent "$@"
        exit 0
        ;;
esac

detect_os() {{
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        echo -e "${{RED}}Sistema operacional nao suportado${{NC}}"
        exit 1
    fi
    echo -e "Sistema detectado: ${{GREEN}}$OS${{NC}}"
}}

preflight_checks() {{
    echo -e "${{YELLOW}}Executando pre-checks (disco e conectividade)...${{NC}}"
    FREE_KB=$(df -Pk "$(dirname "$INSTALL_DIR")" | awk 'NR==2 {{print $4}}' || echo "0")
    if [ "${{FREE_KB:-0}}" -lt 262144 ]; then
        echo -e "${{RED}}Espaco em disco insuficiente. Necessario pelo menos 256MB livres.${{NC}}"
        exit 1
    fi
    if ! curl -fsS --max-time 10 "$PLATFORM_URL/api/health" >/dev/null 2>&1; then
        echo -e "${{RED}}Sem conectividade com a plataforma ($PLATFORM_URL). Verifique DNS/NAT/Firewall.${{NC}}"
        exit 1
    fi
    echo -e "${{GREEN}}Pre-checks OK.${{NC}}"
}}

install_dependencies() {{
    echo -e "${{YELLOW}}Instalando dependencias...${{NC}}"
    case $OS in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq python3 python3-pip curl ca-certificates systemd
            ;;
        centos|rhel|fedora|rocky|almalinux)
            yum install -y python3 python3-pip curl ca-certificates 2>/dev/null || \
            dnf install -y python3 python3-pip curl ca-certificates
            ;;
        alpine)
            apk add --no-cache python3 py3-pip curl ca-certificates
            ;;
    esac
    pip3 install -q psutil 2>/dev/null || true
}}

create_directories() {{
    mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$CONFIG_DIR"
    chmod 750 "$CONFIG_DIR" "$INSTALL_DIR"
    chmod 755 "$LOG_DIR"
}}

write_config() {{
    cat > "$CONFIG_DIR/agent.conf" <<CONF
[las]
platform_url = {platform_url}
agent_token = {token}
role = {role}
modules = {modules_str}
log_dir = /var/log/las
install_dir = /opt/las

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[updates]
enabled = true
check_interval = 3600

[routing]
gateway_urls = {gateway_urls_str}
routing_refresh_interval = 300
gateway_strategy = priority-weighted-failover

[mtls]
enabled = true
required = true
platform_url = __MTLS_PLATFORM_URL__
ca_file = /etc/las/mtls-ca.pem
client_cert_file = /etc/las/mtls-client.pem
client_key_file = /etc/las/mtls-client-key.pem

[transport]
compress_data = true
protect_data = true
protection = mtls

[features]
process_monitor = true
port_scan = true
disk_monitor = true
network_monitor = true
log_collection = true
otel_enabled = true
ids_enabled = false
apm_enabled = false

[log_paths]
paths = /var/log/syslog,/var/log/auth.log,/var/log/nginx/*.log,/var/log/apache2/*.log
CONF
    chmod 600 "$CONFIG_DIR/agent.conf"
}}

bootstrap_mtls() {{
    echo -e "${{YELLOW}}Provisionando certificados mTLS...${{NC}}"
    HOSTNAME_VALUE=$(hostname -f 2>/dev/null || hostname)
    RESPONSE=$(curl -fsSL "$PLATFORM_URL/api/v1/agents/bootstrap/mtls?hostname=${{HOSTNAME_VALUE}}" -H "Authorization: Bearer $AGENT_TOKEN")
    export LAS_MTLS_RESPONSE="$RESPONSE"
    python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["LAS_MTLS_RESPONSE"])
base = Path("/etc/las")
(base / "mtls-ca.pem").write_text(payload["ca_pem"], encoding="ascii")
(base / "mtls-client.pem").write_text(payload["client_cert_pem"], encoding="ascii")
(base / "mtls-client-key.pem").write_text(payload["client_key_pem"], encoding="ascii")
mtls_url = payload.get("mtls_platform_url", "")
if mtls_url:
    conf = base / "agent.conf"
    try:
        conf.write_text(conf.read_text(encoding="utf-8").replace("__MTLS_PLATFORM_URL__", mtls_url), encoding="utf-8")
    except FileNotFoundError:
        pass
PY
    MTLS_PLATFORM_URL=$(python3 - <<'PY'
import json, os
payload = json.loads(os.environ.get("LAS_MTLS_RESPONSE", "{{}}"))
print(payload.get("mtls_platform_url", ""))
PY
    )
    if [ -z "$MTLS_PLATFORM_URL" ]; then MTLS_PLATFORM_URL="{settings.MTLS_PLATFORM_URL}"; fi
}}

download_agent() {{
    echo -e "${{YELLOW}}Baixando agente...${{NC}}"
    DOWNLOADED="0"
    if [ -n "$GATEWAY_URLS" ]; then
      OLDIFS="$IFS"; IFS=','
      for gw in $GATEWAY_URLS; do
        IFS="$OLDIFS"
        gw=$(printf "%s" "$gw" | sed "s/[[:space:]]//g" | sed "s#/*$##")
        if [ -z "$gw" ]; then IFS=','; continue; fi
        echo -e "${{YELLOW}}Tentando baixar via gateway: $gw${{NC}}"
        if curl -fL --retry 2 --retry-connrefused --connect-timeout 8 --max-time 60 --progress-bar \
          --cacert "/etc/las/mtls-ca.pem" \
          --cert "/etc/las/mtls-client.pem" \
          --key "/etc/las/mtls-client-key.pem" \
          "$gw/api/v1/agents/artifacts/linux-agent.py" \
          -o "$INSTALL_DIR/las-agent.py" ; then
          DOWNLOADED="1"
          break
        fi
        IFS=','
      done
      IFS="$OLDIFS"
    fi
    if [ "$DOWNLOADED" != "1" ]; then
      echo -e "${{YELLOW}}Baixando via SaaS (mTLS edge): $MTLS_PLATFORM_URL${{NC}}"
      curl -fL --retry 3 --retry-connrefused --progress-bar \
        --cacert "/etc/las/mtls-ca.pem" \
        --cert "/etc/las/mtls-client.pem" \
        --key "/etc/las/mtls-client-key.pem" \
        "$MTLS_PLATFORM_URL/api/v1/agents/artifacts/linux-agent.py" \
        -H "Authorization: Bearer $AGENT_TOKEN" \
        -o "$INSTALL_DIR/las-agent.py"
    fi
    chmod +x "$INSTALL_DIR/las-agent.py"
}}

install_service() {{
    cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=LAS Agent
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=root
ExecStart=/usr/bin/env python3 $INSTALL_DIR/las-agent.py
StandardOutput=append:$LOG_DIR/agent.log
StandardError=append:$LOG_DIR/agent-error.log
Environment=LAS_CONFIG=$CONFIG_DIR/agent.conf
Environment=NEXUS_CONFIG=$CONFIG_DIR/agent.conf

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl restart $SERVICE_NAME
    sleep 2

    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${{GREEN}}Agente instalado e em execucao.${{NC}}"
    else
        echo -e "${{RED}}Falha ao iniciar o agente. Verifique: journalctl -u $SERVICE_NAME${{NC}}"
        exit 1
    fi
}}

verify_connection() {{
    echo -e "${{YELLOW}}Verificando conectividade com a plataforma...${{NC}}"
    RESPONSE=$(curl -s -o /dev/null -w "%{{http_code}}" "$PLATFORM_URL/api/health")
    if [ "$RESPONSE" = "200" ]; then
        echo -e "${{GREEN}}Plataforma acessivel.${{NC}}"
    else
        echo -e "${{YELLOW}}Nao foi possivel validar a conexao agora (HTTP $RESPONSE).${{NC}}"
    fi
}}

detect_os
preflight_checks
install_dependencies
create_directories
write_config
bootstrap_mtls
download_agent
install_service
verify_connection

echo -e "${{GREEN}}Instalacao concluida.${{NC}}"
echo "Token: $AGENT_TOKEN"
echo "Plataforma: $PLATFORM_URL"
echo "Config: $CONFIG_DIR/agent.conf"
echo "Logs: journalctl -u $SERVICE_NAME -f"
echo "Desinstalar: sudo bash install-las-agent-linux.sh --uninstall"
"""


def build_windows_install_script(
    platform_url: str,
    token: str,
    role: str = "agent",
    modules: list = None,
    gateway_urls: Optional[list[str]] = None,
    expected_sha256: Optional[str] = None,
) -> str:
    """Generate the Windows PowerShell installer with embedded token."""
    modules, features = _agent_features(modules)
    modules_str = ",".join(modules)
    gateway_urls_str = ",".join(gateway_urls or [])
    return f"""# LAS Plataforma de Monitoramento e Observabilidade
$ErrorActionPreference = "Stop"

$PLATFORM_URL = "{platform_url}"
$AGENT_TOKEN = "{token}"
$AGENT_ROLE = "{role}"
$GATEWAY_URLS = "{gateway_urls_str}"
$INSTALL_DIR = "C:\\LASAgent"
$CONFIG_DIR = "C:\\LASAgent\\config"
$LOG_DIR = "C:\\LASAgent\\logs"
$SERVICE_NAME = "LASAgent"
$EXPECTED_SHA256 = "{expected_sha256 or ''}"
$FINAL_EXE = "$INSTALL_DIR\\las-agent.exe"

Write-Host "LAS Plataforma de Monitoramento e Observabilidade" -ForegroundColor Cyan
Write-Host "Instalador do agente Windows" -ForegroundColor Green

if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {{
    Write-Host "Execute o PowerShell como Administrador." -ForegroundColor Red
    exit 1
}}

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

Write-Progress -Activity "LAS Agent" -Status "Gravando configuracao" -PercentComplete 10
@"
[las]
platform_url = {platform_url}
agent_token = {token}
role = {role}
modules = {modules_str}
log_dir = C:\\LASAgent\\logs
install_dir = C:\\LASAgent

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[updates]
enabled = true
check_interval = 3600

[routing]
gateway_urls = {gateway_urls_str}
routing_refresh_interval = 300
gateway_strategy = priority-weighted-failover

[features]
process_monitor = {_as_ini_bool(features["process_monitor"])}
service_monitor = {_as_ini_bool(features["service_monitor"])}
port_scan = {_as_ini_bool(features["port_scan"])}
disk_monitor = {_as_ini_bool(features["disk_monitor"])}
network_monitor = {_as_ini_bool(features["network_monitor"])}
log_collection = {_as_ini_bool(features["log_collection"])}
otel_enabled = {_as_ini_bool(features["otel_enabled"])}
traces_enabled = {_as_ini_bool(features["traces_enabled"])}
rum_enabled = {_as_ini_bool(features["rum_enabled"])}
ids_enabled = {_as_ini_bool(features["ids_enabled"])}
vuln_scan_enabled = {_as_ini_bool(features["vuln_scan_enabled"])}
apm_enabled = {_as_ini_bool(features["apm_enabled"])}

[log_paths]
paths = C:\\LASAgent\\logs\\*.log,C:\\inetpub\\logs\\LogFiles\\*\\*.log

[transport]
compress_data = true
protect_data = true
protection = mtls
"@ | Set-Content -LiteralPath "$CONFIG_DIR\\agent.conf" -Encoding Ascii

$headers = @{{ "Authorization" = "Bearer $AGENT_TOKEN" }}
$artifactTemp = Join-Path $env:TEMP ("las-agent-" + [guid]::NewGuid().ToString() + ".exe")

if (Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue) {{
    Write-Progress -Activity "LAS Agent" -Status "Parando servico anterior" -PercentComplete 18
    Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}}

Write-Progress -Activity "LAS Agent" -Status "Baixando agente" -PercentComplete 30
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {{
    & curl.exe -L --fail --progress-bar `
      -H "Authorization: Bearer $AGENT_TOKEN" `
      "$PLATFORM_URL/api/v1/agents/artifacts/windows-agent.exe" `
      -o $artifactTemp
}} else {{
    Invoke-WebRequest -Uri "$PLATFORM_URL/api/v1/agents/artifacts/windows-agent.exe" `
      -Headers $headers `
      -OutFile $artifactTemp
}}

if (-not (Test-Path $artifactTemp)) {{
    throw "Falha ao baixar o executavel do agente."
}}

$artifactSize = (Get-Item $artifactTemp).Length
if ($artifactSize -lt 1MB) {{
    throw "Executavel baixado com tamanho invalido: $artifactSize bytes"
}}

if ($EXPECTED_SHA256) {{
    $artifactHash = (Get-FileHash $artifactTemp -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($artifactHash -ne $EXPECTED_SHA256.ToUpperInvariant()) {{
        throw "Hash do agente invalido. Esperado: $EXPECTED_SHA256 / Obtido: $artifactHash"
    }}
}}

if (Test-Path $FINAL_EXE) {{
    Remove-Item -Force $FINAL_EXE -ErrorAction SilentlyContinue
}}

Move-Item -Force $artifactTemp $FINAL_EXE
Unblock-File -Path $FINAL_EXE -ErrorAction SilentlyContinue

$nssmPath = "$INSTALL_DIR\\nssm.exe"
if (-not (Test-Path $nssmPath)) {{
    Write-Progress -Activity "LAS Agent" -Status "Baixando NSSM" -PercentComplete 55
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\\nssm.zip"
    Expand-Archive -Path "$env:TEMP\\nssm.zip" -DestinationPath "$env:TEMP\\nssm" -Force
    Copy-Item "$env:TEMP\\nssm\\nssm-2.24\\win64\\nssm.exe" $nssmPath -Force
}}

Write-Progress -Activity "LAS Agent" -Status "Registrando servico" -PercentComplete 75
if (Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue) {{
    & $nssmPath stop $SERVICE_NAME | Out-Null
    & $nssmPath remove $SERVICE_NAME confirm | Out-Null
}}

& $nssmPath install $SERVICE_NAME $FINAL_EXE
& $nssmPath set $SERVICE_NAME AppDirectory $INSTALL_DIR
& $nssmPath set $SERVICE_NAME AppStdout "$LOG_DIR\\agent.log"
& $nssmPath set $SERVICE_NAME AppStderr "$LOG_DIR\\agent-error.log"
& $nssmPath set $SERVICE_NAME Start SERVICE_AUTO_START
& $nssmPath set $SERVICE_NAME AppEnvironmentExtra \"LAS_CONFIG=$CONFIG_DIR\\agent.conf`nNEXUS_CONFIG=$CONFIG_DIR\\agent.conf\"

Write-Progress -Activity "LAS Agent" -Status "Iniciando servico" -PercentComplete 90
Start-Service $SERVICE_NAME

$status = (Get-Service -Name $SERVICE_NAME).Status
Write-Progress -Activity "LAS Agent" -Completed
if ($status -eq "Running") {{
    Write-Host "Agente instalado e em execucao." -ForegroundColor Green
    Write-Host "Token: {token}" -ForegroundColor Yellow
    Write-Host "Plataforma: {platform_url}" -ForegroundColor Cyan
    Write-Host "Config: $CONFIG_DIR\\agent.conf" -ForegroundColor Cyan
    Write-Host "Logs: $LOG_DIR\\agent.log" -ForegroundColor Cyan
}} else {{
    Write-Host "Falha ao iniciar o servico. Verifique os logs." -ForegroundColor Red
    exit 1
}}
"""


def build_gateway_install_script(
    platform_url: str,
    token: str,
    gateway_type: str = "agents",
    gateway_config: Optional[dict] = None,
) -> str:
    """Generate a Linux gateway installer with embedded token."""
    features = _gateway_features(gateway_config)
    syslog_config = (gateway_config or {}).get("syslog") or {}
    syslog_enabled = bool(syslog_config.get("enabled", features.get("syslog", False)))
    syslog_host = syslog_config.get("listen_host", "0.0.0.0")
    syslog_udp_port = int(syslog_config.get("udp_port", 514))
    syslog_tcp_port = int(syslog_config.get("tcp_port", 514))
    syslog_tls_port = int(syslog_config.get("tls_port", 6514))
    return f"""#!/bin/bash
set -e

PLATFORM_URL="{platform_url}"
GATEWAY_TOKEN="{token}"
GATEWAY_TYPE="{gateway_type}"
INSTALL_DIR="/opt/las-gateway"
CONFIG_DIR="/etc/las"
SERVICE_NAME="las-gateway"
MTLS_PLATFORM_URL="{settings.MTLS_PLATFORM_URL}"
PUBLIC_ENDPOINT=""

echo "LAS Plataforma de Monitoramento e Observabilidade"
echo "Instalacao do gateway Linux"

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute como root: sudo bash install-las-gateway-linux.sh"
  exit 1
fi

uninstall_gateway() {{
  echo "Desinstalando gateway Linux..."
  if command -v systemctl >/dev/null 2>&1; then
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  fi
  rm -f "/etc/systemd/system/$SERVICE_NAME.service"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload 2>/dev/null || true
    systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true
  fi
  rm -rf "$INSTALL_DIR"
  if [ "${{2:-}}" = "--purge" ] || [ "${{1:-}}" = "--purge" ]; then
    rm -f "$CONFIG_DIR/gateway.conf"
    echo "Configuracao do gateway removida. Certificados e logs compartilhados foram preservados."
  else
    echo "Configuracao preservada em $CONFIG_DIR/gateway.conf. Use --purge para remover o arquivo de configuracao."
  fi
  echo "Gateway Linux desinstalado."
}}

case "${{1:-}}" in
  --uninstall|uninstall|remove)
    uninstall_gateway "$@"
    exit 0
    ;;
esac

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"

if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq python3 python3-pip curl ca-certificates systemd
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 python3-pip curl ca-certificates systemd
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3 python3-pip curl ca-certificates systemd
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache python3 py3-pip curl ca-certificates
fi

curl -fsSL "$PLATFORM_URL/api/v1/agents/artifacts/gateway.py" \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -o "$INSTALL_DIR/las-gateway.py"
chmod +x "$INSTALL_DIR/las-gateway.py"

HOSTNAME_VALUE=$(hostname -f 2>/dev/null || hostname)
PUBLIC_ENDPOINT="https://${{HOSTNAME_VALUE}}:9443"

cat > "$CONFIG_DIR/gateway.conf" <<CONF
[las]
platform_url = {platform_url}
gateway_token = {token}
type = {gateway_type}
listen_host = 0.0.0.0
listen_port = 9443
public_endpoint = ${{PUBLIC_ENDPOINT}}

[intervals]
heartbeat_interval = 60
task_poll_interval = 20

[updates]
enabled = true
check_interval = 3600

[mtls]
enabled = true
required = true
platform_url = {settings.MTLS_PLATFORM_URL}
ca_file = /etc/las/mtls-ca.pem
client_cert_file = /etc/las/mtls-client.pem
client_key_file = /etc/las/mtls-client-key.pem
server_cert_file = /etc/las/mtls-server.pem
server_key_file = /etc/las/mtls-server-key.pem

[cluster]
cluster_name = default
priority = 100
weight = 1
failover_only = false
shared_with_tenants = false

[transport]
compress_data = true
protect_data = true
protection = mtls

[features]
agent_proxy = {_as_ini_bool(features.get("agent_proxy", False))}
logs = {_as_ini_bool(features.get("logs", False))}
otel = {_as_ini_bool(features.get("otel", False))}
traces = {_as_ini_bool(features.get("traces", False))}
rum = {_as_ini_bool(features.get("rum", False))}
integrations = {_as_ini_bool(features.get("integrations", False))}
database = {_as_ini_bool(features.get("database", False))}
messaging = {_as_ini_bool(features.get("messaging", False))}
itsm = {_as_ini_bool(features.get("itsm", False))}
webhooks = {_as_ini_bool(features.get("webhooks", False))}
security = {_as_ini_bool(features.get("security", False))}
ids = {_as_ini_bool(features.get("ids", False))}
pentest = {_as_ini_bool(features.get("pentest", False))}
network_discovery = {_as_ini_bool(features.get("network_discovery", False))}
snmp = {_as_ini_bool(features.get("snmp", False))}
syslog = {_as_ini_bool(syslog_enabled)}

[syslog]
enabled = {_as_ini_bool(syslog_enabled)}
listen_host = {syslog_host}
udp_port = {syslog_udp_port}
tcp_port = {syslog_tcp_port}
tls_port = {syslog_tls_port}
CONF

RESPONSE=$(curl -fsSL --get "$PLATFORM_URL/api/v1/agents/bootstrap/mtls" \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  --data-urlencode "hostname=${{HOSTNAME_VALUE}}" \
  --data-urlencode "public_endpoint=${{PUBLIC_ENDPOINT}}")
export LAS_MTLS_RESPONSE="$RESPONSE"
python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(os.environ["LAS_MTLS_RESPONSE"])
base = Path("/etc/las")
(base / "mtls-ca.pem").write_text(payload["ca_pem"], encoding="ascii")
(base / "mtls-client.pem").write_text(payload["client_cert_pem"], encoding="ascii")
(base / "mtls-client-key.pem").write_text(payload["client_key_pem"], encoding="ascii")
(base / "mtls-server.pem").write_text(payload["server_cert_pem"], encoding="ascii")
(base / "mtls-server-key.pem").write_text(payload["server_key_pem"], encoding="ascii")
PY

cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=LAS Gateway
After=network.target

[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/env python3 $INSTALL_DIR/las-gateway.py
Environment=LAS_CONFIG=$CONFIG_DIR/gateway.conf
Environment=NEXUS_CONFIG=$CONFIG_DIR/gateway.conf

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME
echo "Gateway instalado. Status: systemctl status $SERVICE_NAME"
echo "Desinstalar: sudo bash install-las-gateway-linux.sh --uninstall"
"""


def build_windows_gateway_install_script(
    platform_url: str,
    token: str,
    gateway_type: str = "agents",
    gateway_config: Optional[dict] = None,
) -> str:
    """Generate a Windows PowerShell gateway installer with embedded token."""
    features = _gateway_features(gateway_config)
    syslog_config = (gateway_config or {}).get("syslog") or {}
    syslog_enabled = bool(syslog_config.get("enabled", features.get("syslog", False)))
    syslog_host = syslog_config.get("listen_host", "0.0.0.0")
    syslog_udp_port = int(syslog_config.get("udp_port", 514))
    syslog_tcp_port = int(syslog_config.get("tcp_port", 514))
    syslog_tls_port = int(syslog_config.get("tls_port", 6514))
    return f"""# LAS Plataforma de Monitoramento e Observabilidade
$ErrorActionPreference = "Stop"

$PLATFORM_URL = "{platform_url}"
$GATEWAY_TOKEN = "{token}"
$GATEWAY_TYPE = "{gateway_type}"
$INSTALL_DIR = "C:\\LASGateway"
$CONFIG_DIR = "C:\\LASGateway\\config"
$LOG_DIR = "C:\\LASGateway\\logs"
$SERVICE_NAME = "LASGateway"
$MTLS_PLATFORM_URL = "{settings.MTLS_PLATFORM_URL}"
$GATEWAY_PUBLIC_ENDPOINT = "https://$([System.Net.Dns]::GetHostByName(($env:COMPUTERNAME)).HostName):9443"

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

@"
[las]
platform_url = {platform_url}
gateway_token = {token}
type = {gateway_type}
listen_host = 0.0.0.0
listen_port = 9443
public_endpoint = $GATEWAY_PUBLIC_ENDPOINT

[intervals]
heartbeat_interval = 60
task_poll_interval = 20

[updates]
enabled = true
check_interval = 3600

[mtls]
enabled = true
required = true
platform_url = {settings.MTLS_PLATFORM_URL}
ca_file = C:\\LASGateway\\config\\mtls-ca.pem
client_cert_file = C:\\LASGateway\\config\\mtls-client.pem
client_key_file = C:\\LASGateway\\config\\mtls-client-key.pem
server_cert_file = C:\\LASGateway\\config\\mtls-server.pem
server_key_file = C:\\LASGateway\\config\\mtls-server-key.pem

[cluster]
cluster_name = default
priority = 100
weight = 1
failover_only = false
shared_with_tenants = false

[transport]
compress_data = true
protect_data = true
protection = mtls

[features]
agent_proxy = {_as_ini_bool(features.get("agent_proxy", False))}
logs = {_as_ini_bool(features.get("logs", False))}
otel = {_as_ini_bool(features.get("otel", False))}
traces = {_as_ini_bool(features.get("traces", False))}
rum = {_as_ini_bool(features.get("rum", False))}
integrations = {_as_ini_bool(features.get("integrations", False))}
database = {_as_ini_bool(features.get("database", False))}
messaging = {_as_ini_bool(features.get("messaging", False))}
itsm = {_as_ini_bool(features.get("itsm", False))}
webhooks = {_as_ini_bool(features.get("webhooks", False))}
security = {_as_ini_bool(features.get("security", False))}
ids = {_as_ini_bool(features.get("ids", False))}
pentest = {_as_ini_bool(features.get("pentest", False))}
network_discovery = {_as_ini_bool(features.get("network_discovery", False))}
snmp = {_as_ini_bool(features.get("snmp", False))}
syslog = {_as_ini_bool(syslog_enabled)}

[syslog]
enabled = {_as_ini_bool(syslog_enabled)}
listen_host = {syslog_host}
udp_port = {syslog_udp_port}
tcp_port = {syslog_tcp_port}
tls_port = {syslog_tls_port}
"@ | Set-Content -LiteralPath "$CONFIG_DIR\\gateway.conf" -Encoding Ascii

$headers = @{{ "Authorization" = "Bearer $GATEWAY_TOKEN" }}
Write-Progress -Activity "LAS Gateway" -Status "Provisionando certificados mTLS" -PercentComplete 15
$hostnameValue = [System.Net.Dns]::GetHostByName(($env:COMPUTERNAME)).HostName
$bootstrapUrl = "$PLATFORM_URL/api/v1/agents/bootstrap/mtls?hostname=$([uri]::EscapeDataString($hostnameValue))&public_endpoint=$([uri]::EscapeDataString($GATEWAY_PUBLIC_ENDPOINT))"
$mtls = Invoke-RestMethod -Uri $bootstrapUrl -Headers $headers -Method Get
$mtls.ca_pem | Set-Content -LiteralPath "$CONFIG_DIR\\mtls-ca.pem" -Encoding Ascii
$mtls.client_cert_pem | Set-Content -LiteralPath "$CONFIG_DIR\\mtls-client.pem" -Encoding Ascii
$mtls.client_key_pem | Set-Content -LiteralPath "$CONFIG_DIR\\mtls-client-key.pem" -Encoding Ascii
$mtls.server_cert_pem | Set-Content -LiteralPath "$CONFIG_DIR\\mtls-server.pem" -Encoding Ascii
$mtls.server_key_pem | Set-Content -LiteralPath "$CONFIG_DIR\\mtls-server-key.pem" -Encoding Ascii
if ($mtls.gateway_public_endpoint) {{
    (Get-Content "$CONFIG_DIR\\gateway.conf" -Raw).Replace("public_endpoint = $GATEWAY_PUBLIC_ENDPOINT", "public_endpoint = $($mtls.gateway_public_endpoint)") | Set-Content -LiteralPath "$CONFIG_DIR\\gateway.conf" -Encoding Ascii
}}

Write-Progress -Activity "LAS Gateway" -Status "Baixando payload" -PercentComplete 35
Invoke-WebRequest -Uri "$PLATFORM_URL/api/v1/agents/artifacts/windows-gateway.exe" `
  -Headers $headers `
  -OutFile "$INSTALL_DIR\\las-gateway.exe"

$nssmPath = "$INSTALL_DIR\\nssm.exe"
if (-not (Test-Path $nssmPath)) {{
    Write-Progress -Activity "LAS Gateway" -Status "Baixando NSSM" -PercentComplete 55
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\\nssm.zip"
    Expand-Archive -Path "$env:TEMP\\nssm.zip" -DestinationPath "$env:TEMP\\nssm" -Force
    Copy-Item "$env:TEMP\\nssm\\nssm-2.24\\win64\\nssm.exe" $nssmPath -Force
}}

Write-Progress -Activity "LAS Gateway" -Status "Registrando servico" -PercentComplete 80
& $nssmPath install $SERVICE_NAME "$INSTALL_DIR\\las-gateway.exe"
& $nssmPath set $SERVICE_NAME AppDirectory $INSTALL_DIR
& $nssmPath set $SERVICE_NAME AppStdout "$LOG_DIR\\gateway.log"
& $nssmPath set $SERVICE_NAME AppStderr "$LOG_DIR\\gateway-error.log"
& $nssmPath set $SERVICE_NAME Start SERVICE_AUTO_START
& $nssmPath set $SERVICE_NAME AppEnvironmentExtra \"LAS_CONFIG=$CONFIG_DIR\\gateway.conf`nNEXUS_CONFIG=$CONFIG_DIR\\gateway.conf\"

Write-Progress -Activity "LAS Gateway" -Status "Iniciando servico" -PercentComplete 95
Start-Service $SERVICE_NAME
Write-Progress -Activity "LAS Gateway" -Completed
Write-Host "Gateway LAS instalado. Verifique com Get-Service $SERVICE_NAME" -ForegroundColor Green
"""
