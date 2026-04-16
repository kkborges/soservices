# Roadmap da Plataforma

## Curto prazo

- corrigir persistencia completa das configuracoes do tenant
- concluir failover automatico do PostgreSQL com proxy ou VIP de escrita
- consolidar o Redis com Sentinel para todos os componentes da plataforma
- ampliar a tela admin com mais metricas da propria plataforma
- validar novamente criacao, edicao e ciclo de vida de tenants

## Proximo bloco funcional

- detalhamento de hosts com consumo por processo
- ativacao de OpenTelemetry por processo suportado
- download guiado de instaladores OTel por tecnologia detectada
- correlacao entre logs, traces, processos e dependencias
- filtros e pesquisa avancada nas telas operacionais

## Infraestrutura e redes

- enriquecer SNMP com interfaces, erros, throughput e modulos
- concluir topologia infra com alertas visuais e drill-down
- classificar hosts descobertos, candidatos e monitorados
- fortalecer discovery, scan e inventario de ativos

## Observabilidade e UX

- RUM com sessoes, tempos de acao e correlacao com servicos
- traces com flow completo do request entre servicos
- synthetic monitoring com fluxos gravados e checks de SSL
- monitoramento de bancos de dados e consultas executadas
- monitoramento de servicos externos e APIs de terceiros

## Seguranca e operacao

- IDS agendado e relatorios de deteccao
- scan de vulnerabilidades e pentest sob demanda
- licenciamento por tipo de monitoramento e consumo
- empacotamento final de instaladores e componentes core
- obfuscacao dos modulos criticos distribuidos

## Empacotamento e producao

- imagem on-premise para server principal e gateway
- cluster final de gateways por tenant com padrao comercial
- automacao de deploy e upgrade por ambiente
- backup, restore e runbooks operacionais
