# LAS Plataforma de Monitoramento e Observabilidade (One-pager)

## O que e
O LAS e uma plataforma para monitorar infraestrutura, logs, observabilidade (OpenTelemetry) e redes (discovery/SNMP) com operacao segura e padronizada, em SaaS ou on-prem.

## Principais modulos
- Infra: hosts Linux/Windows, consumo de recursos e processos.
- Logs: ingestao via agente, gateway e syslog remoto (UDP/TCP 514; 6514 reservado para TLS).
- Observabilidade: ingestao OTel (traces e metricas) com drill down.
- Redes: discovery executado via gateway e coleta SNMP para inventario e interfaces.
- Gateways: cluster/failover por tenant; batching e encaminhamento de dados.
- Suporte: tickets por tenant com triagem automatizada por IA.
- Licenciamento: por modulos (entitlements) para liberar capacidades conforme necessidade.

## Como funciona (alto nivel)
- Usuario acessa `las.<dominio>` (frontend).
- API publica em `api.<dominio>`.
- Agentes preferem enviar para um gateway do tenant (mTLS); sem gateway, fazem fallback para o SaaS/API (mTLS).
- Gateway executa discovery/SNMP dentro da rede do cliente e encaminha lotes para a API.

## Seguranca
- mTLS obrigatorio para trafego operacional (agentes/gateways).
- Recomendacao de separar endpoint publico e endpoint mTLS em DNS e firewall.

## Implantacao
Opcoes:
- Docker Compose (single e HA)
- Kubernetes (Ingress + replicas)
- SaaS (nuvem) ou on-prem (cliente opera)

## Proximo passo (piloto sugerido)
1 gateway + 1 agente + 1 fonte de syslog + 1 aplicacao com OTel (quando aplicavel).

