# Edicoes e Opcoes de Deploy (Cloud e On-Prem)

Este documento padroniza como a plataforma LAS e oferecida em ambiente de cliente (trial e producao).

## Matriz de distribuicao

1. Cloud (SaaS da LAS)
- Orquestracao: Docker (Compose) ou Kubernetes (manifests/Helm).
- Binarios: server, gateways e agentes em Linux e Windows, com instaladores que fazem configuracao e autoupdate.

2. On-Prem (cliente opera o ambiente)
- Orquestracao: Docker (Compose) ou Kubernetes (manifests/Helm).
- Binarios: server, gateways e agentes em Linux e Windows, com instaladores que fazem configuracao e autoupdate.

## Instaladores padrao (agentes e gateways)

Objetivo: minimo de interacao humana, instalacao repetivel e com menos erros.

- Linux: `install-*.sh` ou `install-*.bin` (scripts auto-suficientes).
- Windows: `*Setup.exe` (install/uninstall) com fallback `ps1` quando necessario.
- Download inteligente: quando existir gateway online no tenant, instaladores preferem baixar pelo gateway (mirror/cache), com fallback para o SaaS.

## HA e escalabilidade (todas as edicoes)

Para qualquer edicao (Cloud ou On-Prem), o desenho recomendado suporta HA e crescimento horizontal:

- Frontend: servido atras de um balanceador (Nginx/HAProxy/ALB/ELB/Ingress) com TLS valido.
- API: 2+ instancias em active-active atras de um balanceador, health-check em `/api/health`.
- Banco/cache: PostgreSQL e Redis em modo HA (gerenciado ou cluster operado pelo cliente).
- Gateways: 2 gateways primarios por tenant + 1 gateway de failover (peso/prioridade), com heartbeats para status preciso.

## Notas de naming (padrao LAS)

- Produto e interface: "LAS Plataforma de Monitoramento e Observabilidade".
- Subdominios recomendados:
  - `las.<dominio>` (frontend)
  - `api.<dominio>` (API)
  - `gw-<tenant>-a.<dominio>`, `gw-<tenant>-b.<dominio>`, `gw-<tenant>-failover.<dominio>` (gateways)

