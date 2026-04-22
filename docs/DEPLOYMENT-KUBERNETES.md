# Deploy Kubernetes (Helm) - LAS Plataforma

Este documento descreve o deploy da **LAS Plataforma de Monitoramento e Observabilidade** em Kubernetes usando Helm.

Escopo:

- API (FastAPI) em HA (replicas)
- Frontend (SPA em Nginx) em HA (replicas)
- Ingress para `las.<dominio>` e `api.<dominio>`
- Opcional: Ingress com **mTLS** para agentes/gateways (`mtls-api.<dominio>`)

Observacao: Postgres/Redis em Kubernetes em HA "de verdade" varia por padrao do cliente. Para producao, recomendamos **servicos gerenciados** quando possivel.

## 1) Pre-requisitos

- Cluster Kubernetes (1.25+ recomendado)
- Helm 3
- Ingress Controller (ex.: NGINX Ingress Controller)
- Registro de imagens acessivel pelo cluster

## 2) Build e push das imagens

Exemplos (ajuste registry):

```bash
docker build -t REGISTRY/las-backend:4.0.0 -f backend/Dockerfile backend
docker build -t REGISTRY/las-frontend:4.0.0 -f frontend/Dockerfile frontend
docker push REGISTRY/las-backend:4.0.0
docker push REGISTRY/las-frontend:4.0.0
```

Para maior protecao de codigo (bytecode-only), use o release:

```bash
docker build -t REGISTRY/las-backend-release:4.0.0 -f backend/Dockerfile.release backend
docker push REGISTRY/las-backend-release:4.0.0
```

## 3) Install/upgrade do Helm chart

Chart: `k8s/helm/las-platform`

```bash
kubectl create namespace las
helm upgrade --install las k8s/helm/las-platform -n las \
  --set images.api.repository=REGISTRY/las-backend \
  --set images.api.tag=4.0.0 \
  --set images.frontend.repository=REGISTRY/las-frontend \
  --set images.frontend.tag=4.0.0 \
  --set env.POSTGRES_HOST=SEU_POSTGRES \
  --set env.POSTGRES_PASSWORD=SUA_SENHA_POSTGRES \
  --set env.REDIS_HOST=SEU_REDIS \
  --set env.REDIS_PASSWORD=SUA_SENHA_REDIS \
  --set env.SECRET_KEY=SUA_SECRET_KEY_64_CHARS \
  --set ingress.hosts.web=las.seudominio.com \
  --set ingress.hosts.api=api.seudominio.com
```

## 4) mTLS (Agentes/Gateways)

Recomendacao:

- Browser users usam TLS normal (sem mTLS).
- Agentes/Gateways usam **mTLS** em um host separado: `mtls-api.<dominio>`.
- O endpoint de bootstrap de mTLS deve permanecer no host de API normal:
  `https://api.<dominio>/api/v1/agents/bootstrap/mtls`

### 4.1 Criar secret do CA (client cert verification)

Para NGINX Ingress Controller:

```bash
kubectl -n las create secret generic las-mtls-client-ca --from-file=ca.crt=./ca.pem
```

### 4.2 Ativar o Ingress mTLS

```bash
helm upgrade --install las k8s/helm/las-platform -n las \
  --set mtlsIngress.enabled=true \
  --set mtlsIngress.host=mtls-api.seudominio.com
```

## 5) Validacoes

```bash
kubectl -n las get pods
kubectl -n las get ingress
```

API health:

```bash
curl -fsS https://api.seudominio.com/api/health
```
