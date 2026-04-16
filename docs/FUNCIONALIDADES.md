# Funcionalidades da Plataforma

## Atualizacao operacional: gateway, syslog e discovery

- Syslog remoto: o gateway escuta UDP/TCP 514 e reserva 6514 para syslog TLS; cada mensagem recebida e enviada em lote para a API com origem por IP/hostname.
- Mapeamento de origem syslog: quando um IP ainda nao existe no tenant, a ingestao cria o host/ativo descoberto com `syslog_enabled`.
- Discovery via gateway: novas tasks de discovery e SNMP sao enfileiradas para um gateway online do tenant, executando a varredura dentro da rede do cliente.
- Modulos do gateway: os instaladores novos gravam `logs`, `otel`, `security`, `ids`, `network_discovery`, `snmp` e `syslog` habilitados por padrao.

## Monitoramento de hosts

- Heartbeat de agentes Linux e Windows.
- Cadastro automático de hosts quando o agente inicia.
- Métricas reais de CPU, memória, disco, rede e processos.
- Detalhamento por host, com status de monitoramento, modo infra/logs/OTel e dados de consumo.

## Ativos de rede e SNMP

- Descoberta de hosts e ativos de rede.
- Discovery e refresh SNMP sao despachados para um gateway online do tenant, executando a varredura dentro da rede do cliente.
- Se nenhum gateway online existir, a API mantem fallback local apenas para laboratorio e ambientes sem segmentacao.
- Separação dos grupos `net_discovered` e `net_w_snmp`.
- Coleta SNMP para portas, fabricante, modelo, sistema operacional, status de interfaces e erros.
- Indicação de SYSLOG habilitado quando detectado.

## Logs

- Ingestão via agentes.
- Ingestão via gateways e fontes externas.
- Consulta por host, IP, processo, aplicação, nível, origem, serviço, ação e conteúdo da mensagem.
- Correlação por `trace_id` quando o log estiver vinculado a uma requisição instrumentada.

## Observabilidade

- Ingestão OpenTelemetry de traces e métricas.
- Drill down de traces por serviço, host, URL, método, status, duração e dependências.
- Correlação entre processos, logs, traces, integrações e serviços consumidos.
- Preparação para RUM, testes sintéticos e monitoramento de APIs externas.

## Gateways

- Registro e heartbeat.
- Cluster por tenant com prioridade, peso e failover.
- Recebimento e encaminhamento de lotes reais de logs, métricas e traces.
- Comunicação segura por token de bootstrap e mTLS obrigatório nas rotas operacionais.

## Agentes

- Instalador Linux.
- Instalador Windows `LASAgentSetup.exe`.
- Manifestos Docker e Kubernetes.
- Roteamento com gateway preferencial e fallback direto para o SaaS quando não houver gateway disponível.

## Administração

- Usuários do tenant.
- Configurações do tenant.
- Canais de notificação.
- Emissão e revogação de tokens.
- Gestão de gateways e topologia de cluster/failover.

## Suporte

- Abertura de tickets por tenant.
- Histórico de mensagens e status.
- Atualização pelo administrador da plataforma.
- Análise preliminar automática com IA antes da tratativa humana.
