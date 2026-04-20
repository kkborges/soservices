# Funcionalidades da Plataforma

## Atualizacao operacional: gateway, syslog e discovery

- Syslog remoto: o gateway escuta UDP/TCP 514 e reserva 6514 para syslog TLS; cada mensagem recebida e enviada em lote para a API com origem por IP/hostname.
- Mapeamento de origem syslog: quando um IP ainda nao existe no tenant, a ingestao cria o host/ativo descoberto com `syslog_enabled`.
- Discovery via gateway: novas tasks de discovery e SNMP sao enfileiradas para um gateway online do tenant, executando a varredura dentro da rede do cliente.
- Modulos do gateway: os instaladores gravam `logs`, `otel`, `security`, `ids`, `network_discovery`, `snmp` e `syslog` habilitados por padrao (ajustavel por licenca/config).

## Monitoramento de hosts

- Heartbeat de agentes Linux e Windows.
- Cadastro automatico de hosts quando o agente inicia.
- Metricas reais de CPU, memoria, disco, rede e processos.
- Detalhamento por host com status de monitoramento, modo infra/logs/OTel e dados de consumo.

## Ativos de rede e SNMP

- Descoberta de hosts e ativos de rede.
- Discovery e refresh SNMP sao despachados para um gateway online do tenant, executando a varredura dentro da rede do cliente.
- Se nenhum gateway online existir, a API mantem fallback local apenas para laboratorio e ambientes sem segmentacao.
- Separacao dos grupos `net_discovered` e `net_w_snmp`.
- Coleta SNMP para portas, fabricante, modelo, sistema operacional, status de interfaces e erros.
- Indicacao de SYSLOG habilitado quando detectado.

## Logs

- Ingestao via agentes.
- Ingestao via gateways e fontes externas.
- Consulta por host, IP, processo, aplicacao, nivel, origem, servico, acao e conteudo da mensagem.
- Correlacao por `trace_id` quando o log estiver vinculado a uma requisicao instrumentada.

## Observabilidade

- Ingestao OpenTelemetry de traces e metricas.
- Drill down de traces por servico, host, URL, metodo, status, duracao e dependencias.
- Correlacao entre processos, logs, traces, integracoes e servicos consumidos.
- Preparacao para RUM, testes sinteticos e monitoramento de APIs externas.

## Gateways

- Registro e heartbeat.
- Cluster por tenant com prioridade, peso e failover.
- Recebimento e encaminhamento de lotes reais de logs, metricas e traces.
- Comunicacao segura por token de bootstrap e mTLS obrigatorio nas rotas operacionais.

## Agentes

- Agente unico por SO: o binario/conteudo do agente contem todos os modulos; a instalacao apenas habilita os modulos licenciados e selecionados.
- Instalador Linux.
- Instalador Windows `LASAgentSetup.exe`.
- Manifestos Docker e Kubernetes.
- Roteamento com gateway preferencial e fallback direto para o SaaS quando nao houver gateway disponivel.

## Distribuicao de artefatos (SaaS ou Gateway)

- Artefatos (binarios, scripts e instaladores) ficam disponiveis no SaaS por padrao.
- Se existir ao menos um gateway online no tenant, os instaladores e manifestos tentam baixar primeiro pelo gateway (mirror/cache em mTLS), e em seguida fazem fallback para o SaaS.
- Isso reduz erros de download, elimina dependencia de `.env` e melhora a instalacao em redes segmentadas (sem internet direta nos hosts monitorados).

## Administracao

- Usuarios do tenant.
- Configuracoes do tenant.
- Canais de notificacao.
- Emissao e revogacao de tokens.
- Gestao de gateways e topologia de cluster/failover.

## Suporte

- Abertura de tickets por tenant.
- Historico de mensagens e status.
- Atualizacao pelo administrador da plataforma.
- Analise preliminar automatica com IA antes da tratativa humana.

