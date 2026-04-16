# Failover de Producao

## Objetivo

Este documento descreve a arquitetura recomendada para failover real do servidor principal, PostgreSQL e Redis em ambiente de producao.

## API

Modelo recomendado:

- 2 ou mais instancias da API em `active-active`
- balanceador reverso na frente, como Nginx, HAProxy ou load balancer do provedor
- health-check em `/api/health`
- deploy rolling, mantendo sempre pelo menos 1 instancia saudavel

## PostgreSQL

Modelo recomendado:

- 1 primario
- 1 replica sincronica ou semi-sincronica
- 1 witness ou gerenciador de failover

Opcoes praticas:

- servico gerenciado do provedor
- `Patroni + etcd/Consul`
- `repmgr + keepalived`, quando o cliente preferir operar o cluster

Requisitos:

- backups full e incrementais
- WAL arquivado
- teste periodico de restore
- DNS virtual ou VIP para o endpoint do banco

## Redis

Modelo recomendado:

- 1 primario
- 2 replicas
- 3 sentinels ou servico gerenciado equivalente

Opcoes praticas:

- Redis gerenciado
- Redis Sentinel

Requisitos:

- endpoint unico para a aplicacao
- persistencia conforme criticidade do ambiente
- validacao de reconexao automatica dos workers e da API

## Gateways

Cada tenant deve operar com:

- 2 gateways primarios
- 1 gateway de failover
- opcionalmente fallback para cluster compartilhado do SaaS

## Subdominios

- `las.soservices.com.br`: frontend
- `api.soservices.com.br`: API
- `gw-<tenant>-a.soservices.com.br`: gateway primario A
- `gw-<tenant>-b.soservices.com.br`: gateway primario B
- `gw-<tenant>-failover.soservices.com.br`: gateway de contingencia

## Observabilidade da plataforma

Monitorar no minimo:

- disponibilidade de cada instancia da API
- latencia media e p95 das rotas principais
- erros `5xx`
- fila e conexao com Redis
- lag ou failover do PostgreSQL
- ingestao de logs, metricas e traces por tenant
- heartbeat dos gateways

## Recomendacao final

Para producao comercial, o melhor caminho e:

- API em `active-active`
- PostgreSQL gerenciado ou Patroni
- Redis gerenciado ou Sentinel
- backup automatizado
- teste trimestral de failover
