# Deploy Geral (Cloud e On-Prem)

Este guia consolida o deploy da **LAS Plataforma de Monitoramento e Observabilidade** em qualquer modo:

- Cloud (SaaS da LAS)
- On-Prem (cliente opera o ambiente)
- Orquestracao (Docker Compose / Kubernetes)
- Binarios (API/Server, Gateways e Agentes)

O objetivo e sempre o mesmo: **minima interacao humana**, **mTLS obrigatorio**, e capacidade de **HA e escala horizontal**.

## 1) Topologia de Comunicacao (Fluxo de Acesso)

### Acesso do usuario (frontend + API)

1. Usuario acessa `https://las.<dominio>` pela Internet.
2. O roteador/firewall faz NAT/port-forward para o IP publico do servidor (ou load balancer).
3. Um reverse-proxy na borda (Nginx Proxy Manager, Nginx, HAProxy ou Ingress) termina TLS e roteia:
   - `/` (SPA) -> `las-frontend` (ou `las-frontend-ha`)
   - `/api/*` -> `las-api` (single) ou `las-api-ha` (HA)

### Comunicacao de agentes e gateways

- Agente -> Gateway (preferencial) -> API (ingest) via **mTLS**
- Agente -> API (fallback, quando nao existe gateway) via **mTLS**
- Gateway -> API (batch de logs/metricas/traces/syslog/discovery) via **mTLS**

## 2) DNS e Reverse Proxy (Recomendado)

Subdominios recomendados:

- `las.<dominio>`: frontend
- `api.<dominio>`: API publica (HTTP/JSON + downloads)
- Opcional: `mtls-api.<dominio>`: endpoint dedicado para mTLS (quando voce quiser separar)

Rotas no proxy:

- Host `las.<dominio>` -> upstream `las-frontend-ha:80` (ou `las-frontend:80`)
- Host `api.<dominio>` -> upstream `las-api-ha:80` (ou `las-api:8000`)
- Garantir que `/api/*` NUNCA aponte para o frontend.

## 3) Deploy por Orquestracao (Docker Compose)

### 3.1 Single node (mais simples)

Arquivo: `docker/docker-compose.yml`

```bash
cd docker
docker-compose up -d --build
docker-compose ps
```

Health:

```bash
curl -fsS http://localhost/api/health
```

### 3.2 HA (API active-active)

Arquivo: `docker/docker-compose.ha.yml`

- Sobe `las-api-a`, `las-api-b`
- Sobe `las-api-ha` (nginx LB interno para API)
- Sobe `las-frontend-ha` (nginx para SPA + proxy de `/api`)

```bash
cd docker
cp .env.example .env
# Edite .env com segredos fortes e NAO rotacione depois que volumes do Postgres/Redis forem criados.
docker-compose -f docker-compose.ha.yml up -d --build
docker-compose -f docker-compose.ha.yml ps
```

Importante: em modo HA, nao suba junto o `docker-compose.yml` (single node), para evitar dois Postgres diferentes e confusao de portas/enderecos.

### 3.3 Dados em HA (PostgreSQL + Redis)

Arquivo: `docker/docker-compose.data-ha.yml`

- PostgreSQL com repmgr + pgpool
- Redis com replicas + sentinel + haproxy

```bash
cd docker
cp .env.example .env
docker-compose -f docker-compose.data-ha.yml up -d
docker-compose -f docker-compose.data-ha.yml ps
```

Notas:

- Para producao, priorize Postgres/Redis gerenciados quando possivel.
- Para desenho completo, veja: [FAILOVER-PRODUCAO.md](FAILOVER-PRODUCAO.md).
- Se voce ver erro `password authentication failed for user "repmgr"`, isso indica rotacao de `REPMGR_PASSWORD` depois que o volume ja existia.
  Use o script [scripts/fix-data-ha-repmgr-auth.sh](../scripts/fix-data-ha-repmgr-auth.sh) no host Docker para alinhar a senha sem apagar volumes.

## 4) Deploy por Kubernetes (Visao Geral)

Recomendado para cloud/on-prem com padrao corporativo.

- `Deployment` para API (2+ replicas)
- `Service` interno para API
- `Ingress` (TLS) para `las.<dominio>` e `api.<dominio>`
- Postgres/Redis: servico gerenciado (recomendado) ou operadores/StatefulSets
- Gateways como `Deployment` por tenant, ou como nodes dedicados (dependendo do modelo)

Observacao: a plataforma suporta HA, mas a estrategia final de banco/cache depende do padrao do cliente.

### 4.1 Helm (artefatos no repositorio)

Chart: `k8s/helm/las-platform`

O chart sobe:

- API (replicas)
- Frontend (replicas) com Nginx garantindo que `/api` vai para a API (evita bug de proxy)
- Ingress web (`las.<dominio>`) e API (`api.<dominio>`)
- Opcional: Ingress mTLS (`mtls-api.<dominio>`) para trafego de agentes/gateways

Exemplo (ajuste repositorios e segredos):

```bash
kubectl create namespace las
helm upgrade --install las k8s/helm/las-platform -n las \
  --set images.api.repository=REGISTRY/las-backend \
  --set images.frontend.repository=REGISTRY/las-frontend \
  --set env.POSTGRES_HOST=SEU_POSTGRES \
  --set env.POSTGRES_PASSWORD=SUA_SENHA_POSTGRES \
  --set env.REDIS_HOST=SEU_REDIS \
  --set env.REDIS_PASSWORD=SUA_SENHA_REDIS \
  --set env.SECRET_KEY=SUA_SECRET_KEY_64_CHARS \
  --set ingress.hosts.web=las.seudominio.com \
  --set ingress.hosts.api=api.seudominio.com
```

## 5) Deploy por Binarios (Server/API, Gateways e Agentes)

### 5.1 Onde ficam os artefatos

Os downloads sao servidos pela API (e opcionalmente espelhados por um gateway do tenant).

Exemplos de artefatos (Windows):

- `LASAgentSetup.exe`
- `LASGatewaySetup.exe`

### 5.2 mTLS (Obrigatorio)

- Agentes, gateways e API usam mTLS para autenticacao e criptografia.
- O bootstrap de certificados e feito pelo instalador (setup) e os arquivos ficam no diretorio de runtime configurado.

## 6) Checklists de Producao

- TLS valido nos subdominios (`las.<dominio>`, `api.<dominio>`)
- `SECRET_KEY` forte e rotacionavel
- Postgres e Redis com persistencia e estrategia de backup/restore
- Observabilidade da propria plataforma habilitada (API, filas, DB)
- Gateways em cluster por tenant (2 primarios + 1 failover)

## 7) Documentos Relacionados

- [EDICOES-E-DEPLOY.md](EDICOES-E-DEPLOY.md)
- [TOPOLOGIA-E-HA.md](TOPOLOGIA-E-HA.md)
- [DEPLOYMENT-CLIENTE.md](DEPLOYMENT-CLIENTE.md)
- [PACOTES-E-INSTALADORES.md](PACOTES-E-INSTALADORES.md)
- [SUPORTE-E-COLETA-DE-LOGS.md](SUPORTE-E-COLETA-DE-LOGS.md)
