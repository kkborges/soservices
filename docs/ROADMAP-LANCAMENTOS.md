# Roadmap de Lancamentos (produto)

Este roadmap e orientado a **versoes comerciais** (o que vai para producao) e nao substitui o backlog tecnico.
Objetivo: sair com um **MVP estavel**, e evoluir em releases curtos e previsiveis.

## Principios

- Primeiro, **estabilidade e operacao** (mTLS, instaladores, HA, logs, runbooks).
- Depois, **mais profundidade** (RUM, topologias completas, plugins, DB, synthetics avancados).
- Em comunicacao comercial, separar sempre:
  - "Disponivel agora" (MVP/GA)
  - "Em breve" (Roadmap)

## v1.0 (MVP / GA inicial)

Foco: entregar valor rapido com baixa friccao e alta confiabilidade.

Entregas:
- Autenticacao e multi-tenant (tenant cliente + admin plataforma).
- Gateways por tenant com cluster/failover e heartbeat.
- Agentes Linux/Windows (infra + processos) com instalacao simplificada.
- Logs:
  - ingestao por agente
  - syslog remoto via gateway (UDP/TCP 514)
  - pesquisa basica por host/nivel/contexto
- Observabilidade (OTel):
  - ingestao OTLP com mTLS
  - lista de traces + detalhes essenciais (servico, host, URL, metodo, status, duracao)
- Tela de Hosts:
  - lista + detalhe do host (cards + graficos + preview de logs)
- Documentacao:
  - deploy (SaaS e on-prem)
  - instalacao de agente/gateway
  - troubleshooting (coleta de logs)

Nao entra no v1.0 (fica claramente como roadmap):
- RUM completo (sessoes)
- Synthetics com timings/baseline completo
- Plugins/Extensoes executando queries/coletores customizados

## v1.1 (Redes: discovery + SNMP forte)

Entregas:
- Discovery executado via gateway (dentro da rede do cliente).
- SNMP avancado:
  - inventario de ativos
  - interfaces, throughput, erros, velocidade, status
- Separacao definitiva "Hosts" x "Ativos de rede" (UI e dados).
- Primeira topologia de rede (grafica) usando discovery + SNMP.

## v1.2 (Synthetics + baselines)

Entregas:
- Criacao/edicao de testes sinteticos via UI.
- Timings minimos:
  - DNS
  - connect/TLS handshake
  - TTFB
  - download (recursos quando aplicavel)
- Baseline por teste + alertas por disponibilidade/latencia.
- Correlacao com aplicacoes (quando URLs mapeadas).

## v1.3 (Plugins/Extensoes executaveis via gateway)

Entregas:
- Modelo de extensao:
  - configuracao (secrets/credenciais por tenant)
  - execucao agendada via gateway tipo "integrations"
  - resultado como metricas (unidades/consumo)
- Primeiro pacote de extensoes:
  - PostgreSQL query personalizada -> metrica
  - Webhook (saida)
  - Teams (notificacao)
  - ServiceNow (ticket/incident)

## v1.4 (RUM/DEM + Aplicacoes)

Entregas:
- RUM basico:
  - sessoes
  - tempos de acao
  - erros JS
- Correlacao RUM -> servico/traces/logs quando possivel.
- UI de Aplicacoes com drill down (sem "pagina vazia").

## v1.5 (Seguranca: IDS/Pentest/ Vulnerabilidades)

Entregas:
- IDS por host (quando licenciado) com telas e drill down.
- Vulnerabilidade host (SO) com historico e evidencias.
- Pentest sob demanda/agendado com relatorio e severidade.

## Observacoes comerciais (trial)

- Trial recomendado: 15 dias.
- Onboarding sugerido: 1 gateway + 1 agente + 1 syslog + 1 app OTel.
- Entregavel do trial: inventario + logs + traces + 1 dashboard padrao.

