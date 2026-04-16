# Tenant de validacao e trilha de trial

## Tenant limpo de validacao

- Nome: `LAS Validacao`
- Slug: `las-validacao`
- Usuario inicial: `validacao_las@soservices.com.br`
- Senha inicial: `admin123`
- URL: `https://las.soservices.com.br`

Use este tenant para instalacoes reais de gateways e agentes em maquinas fisicas e virtuais Windows/Linux.

## Links operacionais

- Frontend: `https://las.soservices.com.br`
- API: `https://api.soservices.com.br`
- Health: `https://api.soservices.com.br/api/health`
- mTLS para agentes/gateways: `https://api.soservices.com.br:8443`
- Guia publico: `https://las.soservices.com.br/docs/cliente-validacao.html`

## Laboratorio de aplicacoes

O diretorio `lab/validation-apps` contem apps minimas em:

- .NET
- Java
- PHP/HTML

Execucao:

```bash
cd lab/validation-apps
docker compose up -d --build
```

Endpoints:

- `http://localhost:5081/health`
- `http://localhost:5082/health`
- `http://localhost:5083/health`

## Trial comercial de 15 dias

Fluxo desejado para a proxima etapa:

1. Cliente preenche cadastro de Pessoa Juridica com CNPJ, razao social, nome fantasia, telefone, endereco e contato tecnico.
2. Sistema exige e-mail corporativo, evitando provedores pessoais quando possivel.
3. Plataforma envia link de validacao por e-mail.
4. Apos validacao, o tenant trial e criado com validade de 15 dias.
5. Cliente recebe e-mail com URL, usuario inicial, guia de instalacao e links de download.
6. Admin da plataforma acompanha consumo, licencas, hosts monitorados e tickets.

## Prints

Os prints oficiais foram pausados nesta versao do guia. Depois que o tenant `las-validacao` receber dados reais de agentes/gateways, gere novas capturas de Hosts, Gateways, Logs, Traces e Tickets para compor a documentacao comercial final.

Checklist de evidencias:

- Primeiros Passos com links de instalacao e endpoints oficiais.
- Gateways com heartbeat, cluster, prioridade, failover e endpoint publico.
- Hosts com status online, CPU/RAM e modo de monitoramento.
- Logs e Traces com eventos reais e correlacao por `trace_id`.
- Tickets com abertura, resposta e analise inicial por IA.
