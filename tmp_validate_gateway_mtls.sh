#!/bin/bash
set -euo pipefail
WORKDIR=/tmp/las-mtls-validate
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR/gateway" "$WORKDIR/agent-gw" "$WORKDIR/agent-direct"

API_HTTP=http://127.0.0.1
BOOTSTRAP_HOST=api.soservices.com.br
MTLS_HOST=api.soservices.com.br
GATEWAY_PORT=19443
AGENT_TOKEN="nxa_Ac1VufvjFP4fY7wcAbU6IJtXU0TukWID5nZB0BafY9kAfUzW"
GATEWAY_TOKEN="nxg_ooi9PLnRsPNqUBkgNLQ9hwRxh9AmVD2ySAqaCW4gzHcCIjIh"

python3 --version >/dev/null

curl -fsSL -H "Host: $BOOTSTRAP_HOST" -H "Authorization: Bearer $GATEWAY_TOKEN" --get \
  --data-urlencode "hostname=localhost" \
  --data-urlencode "public_endpoint=https://localhost:${GATEWAY_PORT}" \
  "$API_HTTP/api/v1/agents/bootstrap/mtls" > "$WORKDIR/gateway/bootstrap.json"

python3 - <<'PY'
import json
from pathlib import Path
base = Path('/tmp/las-mtls-validate/gateway')
payload = json.loads((base / 'bootstrap.json').read_text())
(base / 'mtls-ca.pem').write_text(payload['ca_pem'], encoding='ascii')
(base / 'mtls-client.pem').write_text(payload['client_cert_pem'], encoding='ascii')
(base / 'mtls-client-key.pem').write_text(payload['client_key_pem'], encoding='ascii')
(base / 'mtls-server.pem').write_text(payload['server_cert_pem'], encoding='ascii')
(base / 'mtls-server-key.pem').write_text(payload['server_key_pem'], encoding='ascii')
PY

cat > "$WORKDIR/gateway/gateway.conf" <<CONF
[nexus]
nexus_url = https://api.soservices.com.br
gateway_token = ${GATEWAY_TOKEN}
type = infra
listen_host = 127.0.0.1
listen_port = ${GATEWAY_PORT}
public_endpoint = https://localhost:${GATEWAY_PORT}

[intervals]
heartbeat_interval = 600

[mtls]
enabled = true
required = true
platform_url = https://api.soservices.com.br:8443
ca_file = $WORKDIR/gateway/mtls-ca.pem
client_cert_file = $WORKDIR/gateway/mtls-client.pem
client_key_file = $WORKDIR/gateway/mtls-client-key.pem
server_cert_file = $WORKDIR/gateway/mtls-server.pem
server_key_file = $WORKDIR/gateway/mtls-server-key.pem

[cluster]
cluster_name = validation
priority = 1
weight = 1
failover_only = false
shared_with_tenants = false
CONF

nohup env NEXUS_CONFIG="$WORKDIR/gateway/gateway.conf" python3 /srv/las-platform/agents/shared/nexus_gateway.py > "$WORKDIR/gateway/stdout.log" 2>&1 &
GATEWAY_PID=$!
echo $GATEWAY_PID > "$WORKDIR/gateway/pid"
sleep 3

if curl -sk https://127.0.0.1:${GATEWAY_PORT}/health >/dev/null 2>&1; then
  echo "ERROR:no-cert-health-should-fail"
  exit 1
else
  echo "OK:no-cert-health-blocked"
fi

curl -fsSL --cert "$WORKDIR/gateway/mtls-client.pem" --key "$WORKDIR/gateway/mtls-client-key.pem" --cacert "$WORKDIR/gateway/mtls-ca.pem" \
  https://localhost:${GATEWAY_PORT}/health > "$WORKDIR/gateway/health.json"
cat "$WORKDIR/gateway/health.json"

echo "127.0.0.1 api.soservices.com.br" >> /etc/hosts
trap 'sed -i "/127.0.0.1 api.soservices.com.br/d" /etc/hosts; kill $(cat "$WORKDIR/gateway/pid") >/dev/null 2>&1 || true' EXIT

curl -fsSL -H "Host: $BOOTSTRAP_HOST" -H "Authorization: Bearer $AGENT_TOKEN" --get \
  --data-urlencode "hostname=localhost" \
  "$API_HTTP/api/v1/agents/bootstrap/mtls" > "$WORKDIR/agent-gw/bootstrap.json"

python3 - <<'PY'
import json
from pathlib import Path
for name in ['agent-gw','agent-direct']:
    base = Path('/tmp/las-mtls-validate') / name
    payload = json.loads((Path('/tmp/las-mtls-validate/agent-gw/bootstrap.json')).read_text())
    (base / 'mtls-ca.pem').write_text(payload['ca_pem'], encoding='ascii')
    (base / 'mtls-client.pem').write_text(payload['client_cert_pem'], encoding='ascii')
    (base / 'mtls-client-key.pem').write_text(payload['client_key_pem'], encoding='ascii')
PY

cat > "$WORKDIR/agent-gw/agent.conf" <<CONF
[nexus]
nexus_url = https://api.soservices.com.br
agent_token = ${AGENT_TOKEN}
role = agent
log_dir = $WORKDIR/agent-gw
install_dir = $WORKDIR/agent-gw

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[routing]
gateway_urls = https://localhost:${GATEWAY_PORT}
routing_refresh_interval = 9999
gateway_strategy = priority-weighted-failover

[mtls]
enabled = true
required = true
platform_url = https://api.soservices.com.br:8443
ca_file = $WORKDIR/agent-gw/mtls-ca.pem
client_cert_file = $WORKDIR/agent-gw/mtls-client.pem
client_key_file = $WORKDIR/agent-gw/mtls-client-key.pem
CONF

timeout 8s env NEXUS_CONFIG="$WORKDIR/agent-gw/agent.conf" python3 /srv/las-platform/agents/shared/nexus_agent.py > "$WORKDIR/agent-gw/run.log" 2>&1 || true
cat "$WORKDIR/agent-gw/run.log"
grep -q "payload forwarded through gateway" "$WORKDIR/agent-gw/run.log"
echo "OK:agent-forwarded-through-gateway"

cat > "$WORKDIR/agent-direct/agent.conf" <<CONF
[nexus]
nexus_url = https://api.soservices.com.br
agent_token = ${AGENT_TOKEN}
role = agent
log_dir = $WORKDIR/agent-direct
install_dir = $WORKDIR/agent-direct

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[routing]
gateway_urls =
routing_refresh_interval = 9999
gateway_strategy = priority-weighted-failover

[mtls]
enabled = true
required = true
platform_url = https://api.soservices.com.br:8443
ca_file = $WORKDIR/agent-direct/mtls-ca.pem
client_cert_file = $WORKDIR/agent-direct/mtls-client.pem
client_key_file = $WORKDIR/agent-direct/mtls-client-key.pem
CONF

timeout 8s env NEXUS_CONFIG="$WORKDIR/agent-direct/agent.conf" python3 /srv/las-platform/agents/shared/nexus_agent.py > "$WORKDIR/agent-direct/run.log" 2>&1 || true
cat "$WORKDIR/agent-direct/run.log"
grep -q "heartbeat sent" "$WORKDIR/agent-direct/run.log"
echo "OK:agent-direct-to-saas"
