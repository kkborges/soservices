# Deploy Com Caddy (las/api + mTLS)

Este guia explica como publicar a plataforma LAS usando **Caddy** como reverse-proxy, roteando por **domínio**:

- `las.soservices.com.br` (frontend)
- `api.soservices.com.br` (API)
- opcional: `mtls-api.soservices.com.br` (API com **mTLS obrigatório** para agentes/gateways)

## 1) DNS e NAT (visão geral)

1. No DNS, crie registros `A` (ou `CNAME`) apontando para o IP público do seu servidor:
   - `las.soservices.com.br`
   - `api.soservices.com.br`
   - `mtls-api.soservices.com.br` (opcional)
2. No roteador/firewall, faça NAT/liberação de portas para o servidor:
   - `80/tcp` e `443/tcp` (Caddy)
   - se você usar mTLS em porta dedicada: `8443/tcp` (opcional)

## 2) Modo Standalone (sem Docker)

### 2.1 Frontend por arquivos estáticos

No standalone, o frontend está em:

- `.../frontend/public` (dentro do bundle `LAS_*_DEPLOY`)

O Caddy pode servir esses arquivos diretamente (sem Node).

### 2.2 API

No standalone, a API normalmente roda em:

- `http://127.0.0.1:8000` (ajuste se você mudou `--listen-port`)

### 2.3 Exemplo de Caddyfile (standalone)

```caddyfile
las.soservices.com.br {
  root * /srv/las-plataforma/standalone/frontend/public
  file_server
}

api.soservices.com.br {
  reverse_proxy 127.0.0.1:8000
}
```

### 2.4 mTLS obrigatório (recomendado para agentes/gateways)

A melhor prática é **separar** a rota pública (`api.*`) da rota mTLS (`mtls-api.*`) para não quebrar o acesso do navegador.

Exemplo (mTLS via subdomínio em 443):

```caddyfile
mtls-api.soservices.com.br {
  tls {
    client_auth {
      mode require_and_verify
      trusted_ca_cert_file /etc/las/mtls/mtls-ca.pem
    }
  }
  reverse_proxy 127.0.0.1:8000
}
```

Depois, configure a plataforma para usar o endpoint mTLS (variável de ambiente):

- `MTLS_PLATFORM_URL=https://mtls-api.soservices.com.br`

Observação: os arquivos da CA/certs dependem do seu fluxo de emissão. No Docker, eles ficam em `runtime/mtls/`.

## 3) Modo Docker (SaaS/On-prem via Compose)

Se o Caddy roda no **host** e a stack LAS roda em **Docker**, use o overlay:

- `docker/docker-compose.caddy-hostports.yml`

Ele publica os serviços internos para o localhost:

- frontend HA -> `http://127.0.0.1:8080`
- API HA -> `http://127.0.0.1:8081`

Exemplo de Caddyfile (docker):

```caddyfile
las.soservices.com.br {
  reverse_proxy 127.0.0.1:8080
}

api.soservices.com.br {
  reverse_proxy 127.0.0.1:8081
}
```

Para mTLS no Docker, você pode:

1. Continuar usando o `las-mtls-edge` (nginx) em `:8443` (se não houver conflito de porta), ou
2. Migrar o mTLS para o Caddy (mesma estratégia do standalone).

## 4) Gateways/Collector em subdomínios

Normalmente, **gateways e agentes iniciam conexão de saída** para o servidor (SaaS/on-prem). Você só cria domínios extras quando precisa expor algo de forma controlada (por exemplo, um endpoint dedicado mTLS).

Sugestões comuns:

- `api.*` (público para browser e automação)
- `mtls-api.*` (restrito para agentes/gateways, com mTLS)

