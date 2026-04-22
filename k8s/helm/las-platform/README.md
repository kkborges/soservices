# LAS Platform Helm Chart

This chart deploys **LAS Plataforma de Monitoramento e Observabilidade** on Kubernetes:

- API (FastAPI) with N replicas
- Frontend (Nginx) with N replicas
- Ingress for `las.<domain>` and `api.<domain>`
- Optional mTLS Ingress for agent/gateway traffic (`mtls-api.<domain>`)

## Quick start

```bash
kubectl create namespace las
helm upgrade --install las k8s/helm/las-platform -n las \
  --set images.api.repository=YOUR_REGISTRY/las-backend \
  --set images.frontend.repository=YOUR_REGISTRY/las-frontend \
  --set env.POSTGRES_HOST=YOUR_PG_HOST \
  --set env.POSTGRES_PASSWORD=YOUR_PG_PASSWORD \
  --set env.REDIS_HOST=YOUR_REDIS_HOST \
  --set env.REDIS_PASSWORD=YOUR_REDIS_PASSWORD \
  --set env.SECRET_KEY=YOUR_SECRET_KEY \
  --set ingress.hosts.web=las.example.com \
  --set ingress.hosts.api=api.example.com
```

## mTLS (agents/gateways)

If you use NGINX Ingress Controller, you can enable mTLS verification:

1. Create a secret with `ca.crt`:

```bash
kubectl -n las create secret generic las-mtls-client-ca --from-file=ca.crt=./ca.pem
```

2. Enable mTLS ingress:

```bash
helm upgrade --install las k8s/helm/las-platform -n las \
  --set mtlsIngress.enabled=true \
  --set mtlsIngress.host=mtls-api.example.com
```

Bootstrap (`/api/v1/agents/bootstrap/mtls`) should remain on the non-mTLS API host.
