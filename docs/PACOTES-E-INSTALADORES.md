# Pacotes, Instaladores e Cenarios (Cloud e On-Prem)

Este documento descreve como a plataforma LAS distribui agentes, gateways e os pacotes de instalacao para clientes.

## Instaladores disponiveis (por tenant)

Os downloads devem ser feitos com o usuario logado no tenant correto, porque cada arquivo recebe token e parametros especificos daquele tenant.

- Agente Linux (installer): `/api/v1/agents/download/linux?format=sh` ou `/api/v1/agents/download/linux?format=bin`
- Agente Windows: `/api/v1/agents/download/windows` (default `exe`) ou `/api/v1/agents/download/windows?format=ps1`
- Gateway Linux (installer): `/api/v1/agents/download/gateway/linux?format=sh` ou `/api/v1/agents/download/gateway/linux?format=bin`
- Gateway Windows: `/api/v1/agents/download/gateway/windows` (default `exe`) ou `/api/v1/agents/download/gateway/windows?format=ps1`
- Docker Compose do agente: `/api/v1/agents/download/docker`
- Manifesto Kubernetes do agente: `/api/v1/agents/download/k8s`

## Perfis, modulos e licencas (visao geral)

- Perfil `infra`: infraestrutura, processos, servicos e logs. Nao habilita traces, OpenTelemetry ou experiencia do usuario.
- Perfil `complete`: infraestrutura, processos, servicos, logs, traces, OpenTelemetry e experiencia do usuario, desde que o tenant tenha as licencas correspondentes.
- Logs ficam inclusos por padrao em qualquer perfil.
- Modulos individuais podem ser solicitados via `modules=...`, mas a API bloqueia com `403` quando a licenca do tenant nao permitir.

## Tipos de gateway

- `agents`: trafego de agentes, OpenTelemetry, traces, IDS, RUM/DEM e failover dos agentes.
- `integrations`: extensoes/plugins, bancos de dados, filas, ITSMs, webhooks e coletores especializados.
- `logs`: syslog, log forwarding e processamento de logs enviados por servidores/equipamentos.
- `security`: IDS, pentest, discovery de rede, SNMP e eventos de seguranca (conforme licencas e tasks).

## Padrao de instalacao Linux (.sh ou .bin)

Os instaladores Linux sao scripts auto-suficientes (com extensao `.sh` ou `.bin`) e fazem:

- pre-checks (minimo de disco e conectividade com a plataforma)
- bootstrap de certificados mTLS
- escrita de configuracao (secao `[las]` como padrao; leitura de configuracoes legadas quando existir)
- download do payload (preferindo gateway do tenant quando existir, com fallback para o SaaS)
- instalacao como service (`systemd`) e inicializacao
- autoupdate periodico (consulta mTLS e troca segura do payload)

Arquivos e servicos padrao:

- config: `/etc/las/agent.conf` e `/etc/las/gateway.conf`
- agent: `/opt/las`
- gateway: `/opt/las-gateway`
- services: `las-agent` e `las-gateway`

## Windows

- `LASAgentSetup.exe`: instalador do agente Windows (inclui install/uninstall).
- `LASGatewaySetup.exe`: instalador do gateway Windows (inclui install/uninstall).
- Fallback PowerShell:
  - agente: `/api/v1/agents/download/windows?format=ps1`
  - gateway: `/api/v1/agents/download/gateway/windows?format=ps1`

## Comunicacao segura

- Agentes e gateways usam `Authorization: Bearer <token>` no bootstrap e para downloads autenticados quando necessario.
- Bundle mTLS: `/api/v1/agents/bootstrap/mtls` (via endpoint publico da plataforma).
- Trafego operacional usa mTLS obrigatorio (edge mTLS da plataforma).
- Instaladores novos vem com transporte protegido por padrao: mTLS obrigatorio, compressao habilitada e protecao de dados habilitada.
- Quando nao existe gateway disponivel para o tenant, o agente envia direto ao SaaS pela rota mTLS da plataforma.

## Atualizacao automatica (autoupdate)

- Agentes e gateways consultam a plataforma periodicamente pela rota mTLS `/api/v1/agents/updates/check`.
- A plataforma responde a versao mais recente, artefato correto por sistema operacional e `SHA256` esperado.
- O componente baixa o novo payload somente quando houver versao diferente, valida o hash, troca o arquivo local e reinicia o processo/servico.

## Bundles de deploy (SaaS / On-prem / Instaladores)

Para entregar um kit portavel (sem depender do repo completo), os bundles `LAS_*` sao gerados localmente em `releases/`:

```bash
python scripts/build_release_bundles.py
```

Isso cria:
- `LAS_SAAS_DEPLOY_YYYYMMDD.tar.gz`
- `LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz`
- `LAS_INSTALLERS_YYYYMMDD.tar.gz`

Observacao: `releases/` e ignorado no git por padrao (artefatos gerados).
