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

`ImagePullBackOff` normalmente significa que o chart apontou para uma imagem que os nós do cluster não conseguem baixar. As imagens `las-backend-release` e `las-frontend` não são publicadas em registry público por padrão; elas precisam ser buildadas e enviadas para um registry acessível pelo cluster.

Exemplos (ajuste registry):

```bash
docker build -t REGISTRY/las-backend-release:4.1.0 -f backend/Dockerfile.release backend
docker build -t REGISTRY/las-frontend:4.1.0 -f frontend/Dockerfile frontend
docker push REGISTRY/las-backend-release:4.1.0
docker push REGISTRY/las-frontend:4.1.0
```

No Windows/PowerShell:

```powershell
.\scripts\deploy\las-k8s-build-push.ps1 -Registry REGISTRY -Tag 4.1.0
```

No Linux:

```bash
./scripts/deploy/las-k8s-build-push.sh --registry REGISTRY --tag 4.1.0
```

## 3) Install/upgrade do Helm chart

Chart: `k8s/helm/las-platform`

```bash
kubectl create namespace las
helm upgrade --install las k8s/helm/las-platform -n las \
  --set images.api.repository=REGISTRY/las-backend-release \
  --set images.api.tag=4.1.0 \
  --set images.frontend.repository=REGISTRY/las-frontend \
  --set images.frontend.tag=4.1.0 \
  --set env.POSTGRES_HOST=SEU_POSTGRES \
  --set env.POSTGRES_PASSWORD=SUA_SENHA_POSTGRES \
  --set env.REDIS_HOST=SEU_REDIS \
  --set env.REDIS_PASSWORD=SUA_SENHA_REDIS \
  --set env.SECRET_KEY=SUA_SECRET_KEY_64_CHARS \
  --set ingress.hosts.web=las.seudominio.com \
  --set ingress.hosts.api=api.seudominio.com
```

### 3.1 Registry privado

Se o registry exigir autenticacao:

```bash
kubectl -n las create secret docker-registry regcred \
  --docker-server=REGISTRY_HOST \
  --docker-username=USUARIO \
  --docker-password=SENHA \
  --docker-email=admin@seudominio.com
```

Depois inclua no Helm:

```bash
helm upgrade --install las k8s/helm/las-platform -n las \
  --set imagePullSecrets[0].name=regcred \
  --set images.api.repository=REGISTRY/las-backend-release \
  --set images.api.tag=4.1.0 \
  --set images.frontend.repository=REGISTRY/las-frontend \
  --set images.frontend.tag=4.1.0
```

### 3.2 Cluster sem registry externo

Para ambiente fechado, use uma das opcoes:

- subir um registry interno no cluster ou na rede;
- importar as imagens em todos os nós workers/masters que possam executar pods;
- usar um registry do provedor (Harbor, Nexus, GitLab Registry, Docker Registry privado, ECR/ACR/GCR).

Exemplo com containerd em cada nó:

```bash
docker save REGISTRY/las-backend-release:4.1.0 -o las-backend-release.tar
docker save REGISTRY/las-frontend:4.1.0 -o las-frontend.tar
sudo ctr -n k8s.io images import las-backend-release.tar
sudo ctr -n k8s.io images import las-frontend.tar
```

Nesse caso, use `imagePullPolicy=IfNotPresent` e garanta que o nome/tag no Helm seja exatamente igual ao nome importado.

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

Diagnostico de `ImagePullBackOff`:

```bash
kubectl -n las describe pod <pod-api-ou-frontend>
kubectl -n las get events --sort-by=.lastTimestamp | tail -n 30
```

Procure mensagens como:

- `pull access denied`: imagem nao existe ou registry exige login.
- `not found`: repository/tag incorreto.
- `x509 certificate signed by unknown authority`: registry privado usa certificado nao confiado pelos nós.
- `i/o timeout`: nó sem rota/firewall/DNS para o registry.

API health:

```bash
curl -fsS https://api.seudominio.com/api/health
```
