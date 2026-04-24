# LAS Plataforma de Monitoramento e Observabilidade
Resumo executivo e mensagens base para marketing.

## Elevator pitch (1 frase)
O LAS unifica monitoramento de infraestrutura, logs, observabilidade (OpenTelemetry) e redes (discovery/SNMP) com operacao segura (mTLS) e gateways por tenant para ambientes segmentados.

## Para quem e (ICP)
- TI/Infra e NOC/SRE em empresas com ambientes hibridos (cloud + on-prem).
- Operacao que precisa reduzir MTTR correlacionando logs, processos e traces.
- Clientes com redes segmentadas (sem internet nos hosts) que exigem gateway local.
- MSPs e times que precisam de multi-tenant com padrao unico de implantacao.

## Principais beneficios (mensagens curtas)
- **Mais visibilidade**: hosts, processos, logs, traces e rede no mesmo contexto.
- **Menos tempo para resolver**: correlacao por `trace_id` e drill down por servico/host.
- **Operacao em redes fechadas**: discovery/SNMP/syslog executados via gateway do tenant.
- **Seguranca por padrao**: mTLS obrigatorio para agentes/gateways (criptografia + identidade).
- **Escala e resiliencia**: cluster/failover de gateways e HA de API.

## Diferenciais tecnicos (para decisores)
- mTLS end-to-end para rotas operacionais.
- Artefatos (instaladores/manifests) servidos pelo SaaS e opcionais via espelho/caching no gateway.
- Licenciamento por modulos (entitlements) para evoluir por necessidade.

## O que costuma entrar no piloto (sugestao)
- 1 gateway do tenant (dentro da rede do cliente).
- 1 a 3 agentes (Linux/Windows).
- 1 fonte de syslog (equipamento de rede ou servidor).
- 1 aplicacao instrumentada via OpenTelemetry (quando aplicavel).

Entregas tipicas em 7-14 dias:
- inventario e status de hosts/processos
- logs centralizados com filtros
- traces com drill down e correlacao por contexto
- discovery/SNMP para ativos com visibilidade de interfaces (quando SNMP habilitado)

## Deployment (mensagem simples)
O LAS pode ser implantado em:
- SaaS (nuvem) ou on-prem (cliente opera).
- Docker Compose ou Kubernetes.
- Com reverse proxy existente (Nginx Proxy Manager/Nginx/Caddy/Ingress).

## Licenciamento (mensagem comercial)
O licenciamento e modular: o cliente habilita apenas o que precisa (infra, OTel/APM, discovery/SNMP, integracoes, seguranca, experiencia do usuario etc.).

## Proximos passos (CTA)
1. Validar DNS/proxy: `las.<dominio>` e `api.<dominio>`.
2. Subir gateway (rede do cliente) e validar mTLS.
3. Instalar 1 agente e habilitar logs.
4. Instrumentar 1 aplicacao com OTel para traces correlacionados.

## Notas de conformidade (importante para comunicacao)
- Evitar prometer itens que estao em evolucao (ex.: RUM completo, sintetic timings avancados) fora da secao "Roadmap".
- Se precisar, amarrar o discurso em "MVP/Piloto" e "Roadmap" explicitamente.

