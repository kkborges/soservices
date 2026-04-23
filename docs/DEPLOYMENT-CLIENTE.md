# LAS Plataforma de Monitoramento e Observabilidade

## Objetivo

Este guia descreve a implantacao da plataforma em ambiente de cliente, seja em nuvem propria, servidor dedicado ou cenario on-premise.

## Arquitetura base

- `frontend`: interface web da plataforma
- `backend`: API FastAPI, autenticacao, ingestao e tickets
- `postgres`: persistencia transacional
- `redis`: fila e cache
- `gateways`: coleta e encaminhamento de logs, metricas e traces
- `agents`: monitoramento de hosts Linux e Windows

## Modos de implantacao

### 1. Nuvem gerenciada

- publicar `frontend` e `backend` na nuvem escolhida
- expor `80/443` para a interface
- manter `5432` e `6379` privados
- instalar agentes e gateways nos ativos monitorados

### 2. Cliente com infraestrutura propria

- subir a stack Docker em servidor Linux do cliente
- instalar gateways locais para coleta de aplicacoes e redes
- distribuir agentes Linux e Windows conforme necessidade

## Passo a passo recomendado

1. Criar pasta da solucao no servidor, por exemplo `/srv/las-plataforma`
2. Configurar `.env` com URL publica, senhas fortes e credenciais SMTP/IA
3. Subir banco e redis
4. Subir API e frontend
5. Validar `GET /api/health`
6. Acessar com o usuario de plataforma `admin/admin`
7. Validar o tenant operacional `demo` com `demo_las@soservices.com.br/admin`
8. Atualizar configuracoes do tenant
9. Gerar e instalar agentes e gateways
10. Validar ingestao em `Hosts`, `Logs`, `Traces` e `Gateways`
11. Habilitar canais de notificacao e processo de tickets

## Seed inicial

A aplicacao cria automaticamente:

- tenant interno `SOServices Platform Admin`
- usuario `admin/admin` com escopo de plataforma
- tenant operacional `Demo`
- usuario `demo_las@soservices.com.br/admin` com escopo de tenant

Esse seed nao inclui hosts, logs, traces ou metricas de exemplo.

## Alta disponibilidade

- o frontend web deve apontar para `las-frontend-ha`, que entrega a SPA e encaminha chamadas `/api` quando necessario
- a API publica deve apontar para `las-api-ha`, uma borda interna dedicada que balanceia `las-api-a` e `las-api-b`
- o compose base de HA esta em `docker/docker-compose.ha.yml`
- o balanceador interno da API esta em `docker/nginx-api-ha.conf`
- a topologia de gateways por tenant e clusters esta detalhada em `docs/TOPOLOGIA-E-HA.md`
- o failover de banco e cache esta detalhado em `docs/FAILOVER-PRODUCAO.md`

## Validacoes pos-implantacao

- login funcional no frontend
- dashboard sem dados mockados
- criacao e atualizacao de configuracoes
- emissao de instaladores de agentes e gateways
- gateway com modulos `syslog`, `network_discovery` e `snmp` habilitados no arquivo `/etc/las/gateway.conf` ou `C:\LASGateway\config\gateway.conf`
- portas liberadas no firewall do gateway: `9443/TCP` para agentes, `514/UDP`, `514/TCP` e, quando ativado, `6514/TCP` para syslog remoto
- discovery de rede retornando `queued_gateway` quando houver gateway online e atualizado com modulo `network_discovery`; gateways antigos sem esse modulo usam fallback local ate reinstalacao
- criacao, edicao e limpeza de gateways
- status `online`, `stale` e `offline` calculado pelo heartbeat
- abertura de ticket e analise inicial automatica

## Recomendacao operacional

- alterar imediatamente as senhas iniciais
- configurar SMTP real
- definir `OPENAI_API_KEY` para habilitar analise inicial dos tickets
- proteger o acesso com reverse proxy, TLS e firewall
- definir subdominios de producao como `api.soservices.com.br` e `las.soservices.com.br`

## Reverse Proxy (NPM ou Caddy)

Hoje suportamos dois modos de entrada para o `frontend` e para a `API`:

### Modo 1: Nginx Proxy Manager (NPM)

- Use o compose `docker/docker-compose.proxy-manager.yml` (porta `80/443/81`).
- No NPM, crie 2 hosts:
  - `las.soservices.com.br` -> `las-frontend-ha:80` (rede `las-net`)
  - `api.soservices.com.br` -> `las-api-ha:80` (rede `las-net`)
- O mTLS edge (para agentes/gateways/OTLP) fica na porta `8443` (compose `docker/docker-compose.mtls.yml`).

Observacao: se a maquina ja usa `80/443` para outro servico, o NPM nao podera ocupar essas portas.

### Modo 2: Caddy externo (host do provedor)

Quando o provedor ja usa Caddy como reverse proxy (mesmo que `80/443` estejam em uso pelo proprio Caddy),
o correto nao e "redirect" para um container; e `reverse_proxy` para uma porta local publicada pelo Docker.

1. Suba a stack sem o NPM e habilite o overlay de portas para o host:

Exemplo (SaaS/HA release):

- `docker-compose -f docker-compose.data-ha.yml -f docker-compose.ha.release.yml -f docker-compose.mtls.yml -f docker-compose.caddy-hostports.yml up -d`

Isso publica:
- `las-frontend-ha` em `127.0.0.1:8080`
- `las-api-ha` em `127.0.0.1:8081`
- `las-mtls-edge` continua em `127.0.0.1:8443`

2. Adicione no seu `Caddyfile` algo como:

```caddyfile
las.soservices.com.br {
  reverse_proxy 127.0.0.1:8080
}

api.soservices.com.br {
  reverse_proxy 127.0.0.1:8081
}
```

Notas:
- mTLS para agentes/gateways permanece em `https://api.soservices.com.br:8443`.
- Se voce quiser mTLS em `443` no Caddy, o Caddy precisa ser configurado para mTLS na borda (nao e o modo padrao atual).
