# Deploy Portável

Esta versão do projeto foi ajustada para execução fora de `genspark.ai` e sem dependência de `Cloudflare Pages/D1`.

## Stack atual

- Backend: `FastAPI`
- Banco: `PostgreSQL`
- Fila/cache: `Redis`
- Proxy/UI estática: `Nginx`
- Agentes: download dinâmico via API

## Subida rápida

```bash
cd docker
docker compose up -d
```

## Endpoints principais

- Frontend mínimo: `http://SEU_HOST/`
- Health: `http://SEU_HOST/api/health`
- Docs: `http://SEU_HOST/api/docs`
- Bootstrap: `http://SEU_HOST/api/v1/auth/bootstrap`

## Observações

- A UI original completa não está presente neste workspace.
- Os instaladores de agente e gateway são gerados pelo backend.
- O uso agora depende de dados reais vindos de agentes/gateways/OTel ou do banco configurado.
