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
