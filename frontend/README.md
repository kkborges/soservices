# LAS Frontend

Este diretório não contém mais a aplicação `Cloudflare Pages + D1` descrita na documentação anterior. O código original da UI não veio no workspace atual.

O que existe agora:

- `public/index.html`: página operacional mínima, sem dados mock, consumindo `/api/health`
- `Dockerfile`: imagem estática em `nginx`

Objetivo:

- permitir publicação em qualquer nuvem com proxy reverso para o backend
- expor documentação real da API em `/api/docs`
- evitar a dependência anterior de `wrangler`, `D1` e `genspark`

Para subir junto com a stack:

```bash
cd docker
docker compose up -d postgres redis las-api las-frontend
```
