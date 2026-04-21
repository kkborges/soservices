# Topologia e Alta Disponibilidade

## Topologia final por tenant

Cada tenant deve operar com a seguinte estrutura logica:

- 2 gateways primarios no mesmo `cluster_name`
- 1 gateway de failover com `failover_only=true`
- opcionalmente 1 ou mais gateways compartilhados do tenant interno, com `shared_with_tenants=true`

## Politica de roteamento dos agentes

- ordenar por `priority`
- dentro da mesma prioridade, distribuir por `weight`
- gateways `failover_only` entram apenas no fim da cadeia
- gateways compartilhados entram depois dos gateways do proprio tenant
- o agente atualiza a rota em `/api/v1/agents/routing` a cada `300` segundos

## Estados de saude

- `online`: heartbeat dentro da janela esperada
- `stale`: heartbeat atrasado, mas ainda dentro da janela de tolerancia
- `offline`: heartbeat ausente alem da janela de tolerancia

O calculo considera o `heartbeat_interval` informado pelo gateway. Na ausencia desse valor, a plataforma usa os limites padrao atuais.

## Cluster da API

Para a camada principal, o arquivo `docker/docker-compose.ha.yml` sobe:

- `las-api-a`
- `las-api-b`
- `postgres`
- `redis`
- `las-frontend`

O arquivo `docker/nginx-ha.conf` aplica:

- balanceamento `least_conn`
- failover HTTP para `500`, `502`, `503` e `504`
- rate limit separado para API, ingestao e login

## Banco e cache

O compose de HA deixa duas instancias da API atras do frontend, mas nao implementa replicacao automatica de banco e cache por si so.

Para producao, recomenda-se:

- PostgreSQL gerenciado ou replicado pelo cliente
- Redis com sentinels ou servico gerenciado
- backups automatizados
- DNS ou load balancer externo para `api.soservices.com.br` e `las.soservices.com.br`
