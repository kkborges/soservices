# Deploy On-Premise (HA)

Este guia descreve o deploy **on-premise** da **LAS Plataforma de Monitoramento e Observabilidade** com:

- API em HA (2 instancias) com balanceamento
- PostgreSQL em HA (repmgr + pgpool)
- Redis em HA (replicas + sentinel + haproxy)
- mTLS dedicado para agentes/gateways (porta separada)
- Nginx Proxy Manager para acesso do usuario final (HTTP/HTTPS)
- Opcional: agente de self-monitoring e Control Gateway (licencas/updates/tickets)

## 1) Pastas

No host Linux:

- `/srv/las-plataforma/deploy-onpremise/`
  - `docker/`

## 2) Subir Stack

No diretorio `docker/`:

1. Crie o arquivo `docker/.env.onprem`:
   - baseie-se em `docker/.env.onprem.example`
   - use senhas fortes

2. Suba:

```bash
cd /srv/las-plataforma/deploy-onpremise/docker
/usr/local/bin/docker-compose -f docker-compose.onprem-ha.yml up -d --build
```

## 3) Acesso

Como o NPM usa portas configuraveis, por padrao (para permitir side-by-side com o SaaS no mesmo host):

- UI do NPM: `http://<host>:8181`
- HTTP: `http://<host>:8080`
- HTTPS: `https://<host>:8443`
- mTLS (agentes/gateways): `https://<host>:9443`

## 4) Configurar Reverse Proxy (NPM)

Crie 2 Proxy Hosts apontando para os containers:

- `las-onprem.local` -> forward para `las-frontend-ha:80`
- `api-onprem.local` -> forward para `las-api-ha:80`

Observacao: o endpoint mTLS **nao** e terminado pelo NPM (precisa do Nginx mTLS edge).

## 5) Self-monitoring e Control Gateway

Os servicos existem no compose:

- `las-self-agent` (self-monitoring) roda com `pid: host` e `privileged: true`.
- `las-control-gateway` (profile `edge`) conecta no SaaS e executa `/api/v1/edge/sync`.

Para subir o control gateway:

```bash
/usr/local/bin/docker-compose -f docker-compose.onprem-ha.yml --profile edge up -d --build
```

Depois, preencha `gateway_token` em `docker/onprem-control-gateway.conf` (token gerado pelo SaaS via `/api/v1/edge/register`).

