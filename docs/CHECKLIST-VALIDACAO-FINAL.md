# Checklist de Validacao Final (LAS)

Data: 2026-04-22  
Branch: `develop`  
Ultimos commits (referencia): `56b3a3b`, `e6a40f6`, `1b35d29`

Este checklist e um registro do que foi validado no repositorio + checagens de disponibilidade publica (HTTP) das URLs. Onde houver "PENDENTE", e porque depende de ambiente/daemon externo (Docker rodando, acesso ao servidor, etc.).

## 1) Repositorio e Qualidade Basica

- [OK] `git status` limpo (sem arquivos modificados pendentes).
- [OK] Compile check: `python -m compileall -q backend/app agents/shared`.
- [OK] Busca por mock de monitoramento:
  Encontrado apenas referencia textual "sem mock" no frontend. Nao ha seed/mock de dados de monitoramento no codigo.

## 2) Documentacao

- [OK] Validador de links em `docs/`:
  `python scripts/validate_docs_links.py`
- [OK] Links corrigidos em `docs/ARCHITECTURE.md` (Contributing, Testing Guide, Quick Start, Deployment).

## 3) Artefatos (Binarios e Setups)

Arquivos presentes em `backend/releases/`:

- [OK] `LASAgentSetup.exe` e `LASGatewaySetup.exe`
  Observacao: o bootstrap suporta uninstall via `/uninstall` e registra em "Programs and Features" (ver `installer/windows/las_setup_bootstrap.py`).
- [OK] `las-agent-windows-x64.exe` e `las-gateway-windows-x64.exe`
  Smoke-test local: executaveis iniciam sem erro de PyInstaller "embedded PKG archive" (mensagem esperada: "Configuration file not found").
- [OK] `las-agent-linux-x64.bin` e `las-gateway-linux-x64.bin`
  Validacao feita por presenca e roteamento de download (ver itens 4/5). Execucao real depende de host Linux.

## 4) Docker Compose (Sintaxe e Variaveis)

Arquivos validados com `docker compose ... config -q` (usando `.env.example`/`.env.onprem.example` como base):

- [OK] `docker/docker-compose.yml`
- [OK] `docker/docker-compose.ha.yml`
- [OK] `docker/docker-compose.ha.images.yml`
- [OK] `docker/docker-compose.ha.release.yml`
- [OK] `docker/docker-compose.data-ha.yml`
- [OK] `docker/docker-compose.proxy-manager.yml`
- [OK] `docker/docker-compose.onprem-ha.yml`
- [OK] `docker/docker-compose.onprem-ha.images.yml`
- [OK] `docker/docker-compose.onprem-ha.release.yml`
- [OK] `docker/docker-compose.mtls.yml`

Observacao importante:
- Os compose referenciam `env_file: .env` / `.env.onprem`. Em primeira instalacao, copiar de `docker/.env.example` e `docker/.env.onprem.example`.

## 5) Endpoints Publicos (Health e Docs)

Checagem DNS (A record):
- `las.soservices.com.br` -> `189.36.244.176`
- `api.soservices.com.br` -> `189.36.244.176`

Checagens (a partir deste ambiente):

- [OK] Frontend via HTTP: `http://las.soservices.com.br` retornou `200`.
- [OK] API via HTTP:
  `http://api.soservices.com.br/api/health` retornou `200`.
  `http://api.soservices.com.br/api/docs` retornou `200`.
  `http://api.soservices.com.br/api/openapi.json` retornou `200` e `openapi=3.1.0` (titulo LAS e versao `4.1.0`).
- [PENDENTE/PROBLEMA] HTTPS (443) esta com falha de handshake TLS (curl Schannel `SEC_E_ILLEGAL_MESSAGE`).
  Impacto: acesso seguro pelo browser (https) nao funciona hoje; somente http (80) responde.
  Proximo passo: revisar NAT/firewall para 443 e/ou a configuracao/certificado no Nginx Proxy Manager.

## 6) Downloads de Agentes/Gateways (sem credenciais)

Sem token (nao autenticado), os endpoints retornam `401` (esperado):

- `GET http://api.soservices.com.br/api/v1/agents/download/linux?...` -> 401
- `GET http://api.soservices.com.br/api/v1/agents/download/windows?...` -> 401
- `GET http://api.soservices.com.br/api/v1/agents/download/docker?...` -> 401
- `GET http://api.soservices.com.br/api/v1/agents/download/k8s?...` -> 401
- `GET http://api.soservices.com.br/api/v1/agents/artifacts/windows-agent.exe` -> 401
- `GET http://api.soservices.com.br/api/v1/agents/artifacts/windows-gateway.exe` -> 401

Atualizacao aplicada no codigo:
- [OK] Linux agora usa artefatos binarios para updates/instalacao (agent/gateway): `linux-agent.bin` e `linux-gateway.bin` (commit `e6a40f6`).
  Observacao: isso exige redeploy do backend para valer no ambiente publicado.

## 7) Nginx Proxy Manager (NPM)

No repositorio:
- [OK] Compose do NPM: `docker/docker-compose.proxy-manager.yml` expoe `80/81/443`.

No ambiente publicado (externo):
- [PENDENTE] Validacao do painel do NPM e proxy-host rules (depende de acesso ao servidor).
- [PROBLEMA] 443 publico falhando handshake (ver item 5).

## 8) Kubernetes (Helm)

- [OK] Chart presente em `k8s/helm/las-platform/` (Chart.yaml, values.yaml e templates).
- [PENDENTE] `helm lint` / `helm template` (o binario `helm` nao esta disponivel neste ambiente de validacao).

## 9) Observacoes de Risco / Pontos para Validacao no Servidor

- HTTPS 443: corrigir para acesso seguro (LetsEncrypt ou certificado proprio no NPM) e garantir que o roteador/NAT encaminha 443 para o host correto.
- Docker runtime: este ambiente nao tinha daemon Docker acessivel para smoke-run de containers (`docker run` falhou por falta do engine). A sintaxe do compose foi validada, mas o "up" precisa ser validado no servidor alvo.
- Syslog 514/6514: validar em gateway Linux/Windows (porta privilegiada 514 pode exigir root/capabilities dependendo de como o servico foi instalado).

