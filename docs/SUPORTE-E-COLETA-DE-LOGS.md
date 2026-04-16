# Suporte, Tickets e Coleta de Logs

## Syslog remoto via gateway

- Configure equipamentos de rede, firewalls, appliances e servidores syslog para enviar eventos ao gateway do tenant.
- Portas padrao do gateway: `514/UDP`, `514/TCP` e reserva `6514/TCP` para syslog TLS.
- A origem e mapeada por IP/hostname; se ela ainda nao existir, a plataforma cria um host/ativo descoberto com `syslog_enabled`.
- Para validar no Linux: `sudo ss -lntup | grep -E ':514|:6514'`.
- Para acompanhar ingestao: `journalctl -u las-gateway -f` e a tela `Logs` do tenant.

## Fluxo de atendimento

1. O cliente abre um ticket dentro do tenant.
2. O ticket passa por análise inicial automática.
3. O administrador recebe o ticket enriquecido com resumo, causa provável e ações recomendadas.
4. O administrador atualiza o ticket com tratativas e próximos passos.
5. O cliente acompanha o histórico diretamente no portal.

## O que informar no ticket

- Título objetivo do problema.
- Severidade.
- Ambiente afetado.
- Serviço, host, aplicação ou ativo impactado.
- Descrição do erro.
- Evidências e logs coletados.
- Horário aproximado da falha.
- Mudanças recentes de configuração, deploy ou rede.

## Coleta de logs no Linux

```bash
journalctl -u nome-do-servico --since "2 hours ago"
tail -n 200 /var/log/syslog
tail -n 200 /var/log/auth.log
```

Também colete logs específicos da aplicação, webserver, banco ou fila quando existirem.

## Coleta de logs no Windows

- Event Viewer: `Application`, `System` e `Security`.
- Logs da aplicação em `C:\ProgramData` ou no diretório do serviço.
- Status do serviço via `services.msc`.
- Status do serviço via PowerShell: `Get-Service NomeDoServico`.

## Coleta de traces e métricas

- Validar se o gateway está recebendo POSTs em `/traces`, `/metrics` ou `/batch`.
- Validar se o endpoint central está recebendo lotes em `/api/v1/ingest/gateway/batch`.
- Conferir os dados nas telas `Logs`, `Traces`, `Hosts` e `Gateways`.

## Consulta de logs

O painel de logs deve permitir buscas por:

- Host ou hostname.
- IP de origem ou destino.
- Processo.
- Aplicação.
- Serviço.
- Ação.
- Nível de severidade.
- Texto livre na mensagem.
- `trace_id` para correlação com observabilidade.

Exemplos da linguagem de consulta planejada:

```text
host = "srv-web-01" and level in ("error", "critical")
ip = "10.0.0.15" and process = "nginx"
application = "portal" and action = "login"
trace_id = "abc123"
message contains "timeout"
```

## Links úteis

- Plataforma: `https://las.soservices.com.br`.
- API: `https://api.soservices.com.br`.
- Health check: `https://api.soservices.com.br/api/health`.
- Guia de validação do cliente: `https://las.soservices.com.br/docs/cliente-validacao.html`.
