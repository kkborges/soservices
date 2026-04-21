# Licenciamento e Edge (Gateway de Controle)

Este documento descreve:

- como o licenciamento funciona em SaaS e on-prem
- como gerar e ativar chaves de licenca
- como funciona o "Gateway de Controle" (Edge) para on-prem
- como o Edge faz validacao e sincronizacao a cada 5 minutos, com mTLS obrigatorio

## Conceitos

### Licencas (codigos)

O backend usa codigos de licenca (entitlements) para liberar modulos:

- `infra`: infraestrutura, processos e servicos
- `complete`: OTel + traces (APM)
- `user_experience`: RUM/DEM (experiencia do usuario)
- `sec`: IDS no host + tasks de seguranca
- `vulnerability_hosts`: scan de vulnerabilidade do host (SO)
- `integrations`: integracoes/plug-ins (bancos, ITSM, webhooks etc)
- `network_discovery`: discovery/scan de rede via gateway
- `snmp_logs`: SNMP + syslog/logs remotos
- `pentest`: tarefas de pentest
- `included`: usado internamente para itens sempre inclusos (ex.: logs basicos)
- `no_user_experience`: remove `user_experience` quando necessario

Observacao: o catalogo e o mapeamento perfil->modulos ficam em `backend/app/services/license_service.py`.

### Perfis do agente

- `infra`: infra + processos + servicos + logs (sem OTel/traces/RUM)
- `complete`: tudo acima + OTel + traces + RUM (quando licenciado)

Logs ficam inclusos por padrao em qualquer perfil.

### Tipos de gateway

- `agents`: proxy/failover para agentes, OTel, traces, IDS, RUM/DEM
- `integrations`: extensoes/plugins (bancos, filas, ITSM, webhooks)
- `logs`: syslog e log forwarding
- `security`: IDS/pentest/discovery/snmp (conforme licencas)
- `control`: gateway de controle (Edge) para ambientes on-prem

## Chaves de licenca (LicenseKey)

As chaves de licenca ficam na tabela `license_keys` (modelo `LicenseKey`).

### SaaS (nuvem)

No SaaS, o superadmin cria chaves e vincula a um tenant cliente.

Endpoints:

- `GET /api/v1/licenses/keys` (superadmin): lista chaves
- `POST /api/v1/licenses/keys` (superadmin): cria chave
- `GET /api/v1/licenses/catalog`: catalogo de codigos e perfis

### On-prem (cliente)

Em on-prem, o tenant pode armazenar a chave localmente para fins de auditoria/ativacao:

- `POST /api/v1/licenses/activate` (admin): grava `tenant.license_key`

O Edge (gateway de controle) pode validar online contra o SaaS e sincronizar limites/entitlements.

## Edge (Gateway de Controle) para on-prem

Objetivo:

- validar licencas no SaaS
- consultar updates de agentes/gateways/extensoes
- monitorar a propria instalacao on-prem (self-monitoring)
- abrir tickets automaticamente quando houver falhas recorrentes

### mTLS obrigatorio

O Edge utiliza o endpoint mTLS (`MTLS_PLATFORM_URL`) para sincronizacao e tickets:

- bootstrap do bundle mTLS: `GET /api/v1/agents/bootstrap/mtls` (TLS normal, sem client-cert)
- sincronizacao: `GET /api/v1/edge/sync` (mTLS obrigatorio)
- tickets: `POST /api/v1/edge/tickets` (mTLS obrigatorio)

### Registro on-prem -> SaaS (opcional)

Quando a instalacao on-prem precisa se registrar no SaaS (por exemplo, para criar o gateway de controle no tenant espelho), use:

- `POST /api/v1/edge/register`

Payload:

```json
{
  "license_key": "laslic_...",
  "tenant_slug": "cliente-xyy",
  "instance_name": "onprem",
  "public_endpoint": "https://gw-control.exemplo.com.br:9443"
}
```

Retorno:

- token do gateway de controle (`control_gateway.token`)
- dados do tenant cliente e do tenant espelho (`slug-0`)
- instrucoes de bootstrap mTLS e polling

### Tenant espelho (slug `-0`)

Para cada tenant cliente `xyz`, o SaaS cria (ou garante) um tenant interno `xyz-0`.

Esse tenant espelho e usado para:

- observabilidade/diagnostico do ambiente LAS relacionado ao cliente
- ingestao de self-monitoring do Edge em on-prem

O seed e a criacao de tenants garantem esse espelho automaticamente:

- `backend/app/services/mirror_tenant_service.py`

### Auto-ticket com IA

Quando necessario, o Edge abre tickets via `POST /api/v1/edge/tickets`.
O backend executa a triagem por IA usando `ticket_ai_service.py` antes do ticket aparecer na UI.

## Boas praticas

- Em producao, exponha `PLATFORM_URL` (TLS publico) para bootstrap do bundle mTLS.
- Mantenha o mTLS (`MTLS_PLATFORM_URL`) acessivel apenas para agentes/gateways (firewall e rate-limit).
- No on-prem, use ao menos 1 gateway `control` e 2 gateways `agents` (primarios) + 1 `failover`.

