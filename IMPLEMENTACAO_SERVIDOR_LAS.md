# Guia de Implementacao - LAS Platform (Servidor Linux)

Este documento descreve um deploy padrao da **LAS Plataforma de Monitoramento e Observabilidade** em um servidor Linux, usando Docker Compose.
Ele foi escrito para ser reutilizavel em qualquer ambiente (cloud ou on-premises), sem conter IPs, usuarios ou senhas reais.

## Requisitos

- Linux x86_64
- Docker Engine + Docker Compose v2
- Portas liberadas (exemplo):
  - `80/tcp` (frontend)
  - `443/tcp` (frontend/API via proxy TLS, quando aplicavel)
  - `8000/tcp` (API direta, apenas se voce expor sem proxy)
  - `5432/tcp` (PostgreSQL, apenas rede interna)
  - `6379/tcp` (Redis, apenas rede interna)

## Estrutura Recomendada no Servidor

- `/srv/las-plataforma` (codigo, compose e estrutura de deploy)
- `/srv/las-plataforma-data` (volumes persistentes, opcional)

## Deploy (Stack Completa - Compose)

1. Clonar o repositorio (ou copiar o codigo) para o servidor:

```bash
sudo mkdir -p /srv/las-plataforma
sudo chown -R $USER:$USER /srv/las-plataforma
cd /srv/las-plataforma

# Exemplo:
# git clone <URL_DO_REPOSITORIO> .
```

2. Subir o stack (modo "single node"):

```bash
cd /srv/las-plataforma/docker

# Ajuste variaveis em um arquivo .env (opcional)
# export POSTGRES_PASSWORD=...
# export SECRET_KEY=...

docker compose up -d --build
docker compose ps
```

3. Health-checks:

```bash
curl -fsS http://localhost/api/health
curl -fsS http://localhost/ | head
```

## Observacoes Importantes

- Para producao, recomendamos colocar um reverse-proxy/ingress na frente (TLS, rate-limit, WAF, etc).
- Para HA (API em duas instancias + dados com failover), veja:
  - [docs/TOPOLOGIA-E-HA.md](docs/TOPOLOGIA-E-HA.md)
  - [docs/FAILOVER-PRODUCAO.md](docs/FAILOVER-PRODUCAO.md)
  - [docs/EDICOES-E-DEPLOY.md](docs/EDICOES-E-DEPLOY.md)

## Troubleshooting Rapido

- Ver logs:

```bash
cd /srv/las-plataforma/docker
docker compose logs -f --tail 200
```

- Rebuild completo:

```bash
docker compose down
docker compose up -d --build
```
