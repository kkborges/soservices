# Instalador Unificado e Fluxo Trial

Este documento define o modelo de distribuicao unico da LAS Plataforma de Monitoramento e Observabilidade para SaaS, on-premise, Docker/Kubernetes e instalacoes standalone.

## Objetivo

O cliente deve receber um unico kit por sistema operacional e licenca. A partir dele, escolhe se vai instalar:

- servidor principal LAS em Docker Compose, Kubernetes ou standalone;
- gateway LAS;
- agente LAS;
- componentes usando SaaS ou ambiente on-premise.

O instalador respeita a licenca informada. Modulos nao contratados ficam indisponiveis, exceto em tenants `trial`, que recebem a licenca full por 15 dias.

## Artefato principal

O comando abaixo gera todos os pacotes:

```bash
python scripts/build_release_bundles.py
```

Saida esperada em `releases/`:

- `LAS_SAAS_DEPLOY_YYYYMMDD.tar.gz`: conteudo de deploy SaaS/orquestrado.
- `LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz`: conteudo de deploy on-premise/orquestrado.
- `LAS_INSTALLERS_YYYYMMDD.tar.gz`: instaladores e payloads de agentes/gateways/server standalone.
- `LAS_PLATFORM_INSTALLER_YYYYMMDD.tar.gz`: kit universal contendo os tres pacotes acima e os entrypoints unificados.

## Entrypoints

Linux:

```bash
sudo ./installer/linux/las-platform-installer.sh install \
  --target server \
  --deployment onprem \
  --runtime compose \
  --bundle ./bundles/LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz \
  --install-dir /srv/las-plataforma/onprem
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\windows\install-las-platform.ps1 `
  -Action install `
  -Target server `
  -Deployment onprem `
  -Runtime compose `
  -Bundle .\bundles\LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz `
  -InstallDir C:\LASPlatform
```

## Modos de instalacao do servidor

### SaaS orquestrado

Use `--deployment saas --runtime compose` ou `--deployment saas --runtime kubernetes`.

Indicado para a nuvem da plataforma, com balanceadores, DNS publico e controle centralizado de tenants.

Para Kubernetes, antes do Helm, faca build/push das imagens para um registry acessivel pelo cluster:

```bash
./scripts/deploy/las-k8s-build-push.sh --registry REGISTRY/las --tag 4.1.0
```

Em seguida use `--set images.api.repository=REGISTRY/las/las-backend-release` e `--set images.frontend.repository=REGISTRY/las/las-frontend` no Helm.

### On-premise orquestrado

Use `--deployment onprem --runtime compose` ou `--deployment onprem --runtime kubernetes`.

Indicado para cliente que quer executar a stack completa localmente, com gateways locais e opcionalmente um gateway de controle conectado ao SaaS.

Em cluster on-premise sem registry externo, use um registry interno ou importe as imagens em todos os nós. Se as imagens nao estiverem acessiveis, os pods ficarao em `ImagePullBackOff`.

### Standalone sem Docker

Use `--runtime standalone`. O instalador sobe:

- `las-api`;
- `las-worker`;
- `las-beat`;
- opcionalmente Postgres local;
- opcionalmente Redis local;
- opcionalmente OTel Collector local.

Exemplo Linux tudo local:

```bash
sudo ./installer/linux/las-platform-installer.sh install \
  --target server \
  --deployment onprem \
  --runtime standalone \
  --bundle ./bundles/LAS_ONPREM_DEPLOY_YYYYMMDD.tar.gz \
  --install-dir /srv/las-plataforma/standalone \
  --postgres local \
  --redis local \
  --collector local
```

## Instalacao de agentes e gateways pelo instalador unico

Para agentes e gateways, o instalador autentica na API do tenant, baixa o instalador correto e executa o bootstrap com token, mTLS, compressao e modulos licenciados.

Agente Linux completo:

```bash
sudo ./installer/linux/las-platform-installer.sh install \
  --target agent \
  --api-url https://api.soservices.com.br \
  --username usuario@cliente.com.br \
  --password 'senha' \
  --profile complete
```

Gateway de logs Linux:

```bash
sudo ./installer/linux/las-platform-installer.sh install \
  --target gateway \
  --api-url https://api.soservices.com.br \
  --username usuario@cliente.com.br \
  --password 'senha' \
  --gateway-type logs \
  --gateway-name gateway-logs-principal
```

No Windows, use `install-las-platform.ps1` com `-Target agent` ou `-Target gateway`.

## Licenciamento

O instalador aceita:

- `--license-file license.json`;
- `--license-key <codigo>`.

Formato recomendado do `license.json`:

```json
{
  "license_key": "laslic_xxx",
  "plan": "enterprise",
  "modules": ["infra", "complete", "sec", "user_experience", "network_discovery", "snmp_logs", "integrations"],
  "limits": {
    "max_hosts": 500,
    "max_agents": 500,
    "max_network_assets": 200
  },
  "expires_at": "2027-04-28T00:00:00Z"
}
```

Regras atuais:

- `trial`: todos os modulos liberados por 15 dias.
- `starter`: infra e SNMP/logs.
- `professional`: infra, complete, discovery, SNMP/logs e integracoes.
- `enterprise`: full, incluindo seguranca, pentest e experiencia do usuario.
- Logs permanecem inclusos em todos os perfis.

## Fluxo trial SaaS

Endpoint publico:

```http
POST /api/v1/trial/signup
```

Payload:

```json
{
  "full_name": "Cliente Teste",
  "email": "cliente@empresa.com.br",
  "password": "SenhaForte123!",
  "company_name": "Empresa Teste",
  "cnpj": "00.000.000/0001-00",
  "phone": "+55 11 99999-9999",
  "requested_features": ["infra", "otel", "rum", "synthetics"],
  "tenant_slug": "empresa-teste"
}
```

Resultado:

- cria tenant trial com licenca full;
- cria usuario admin usando o e-mail informado;
- cria chave trial com validade de 15 dias;
- cria tenant espelho `slug-0` para monitoramento da propria plataforma;
- envia e-mail quando SMTP estiver configurado;
- retorna URL sugerida do tenant.

## DNS de tenants

Recomendacao para producao:

- `las.soservices.com.br`: frontend principal;
- `api.soservices.com.br`: API publica;
- `*.las.soservices.com.br`: tenants trial e tenants de clientes;
- `mtls-api.soservices.com.br`: borda mTLS para agentes/gateways.

O registro wildcard `*.las.soservices.com.br` evita criar DNS manual para cada trial. Caso o provedor nao permita wildcard, crie o subdominio retornado pelo endpoint `trial/signup`.

## Interface grafica

O desenho final recomendado e ter uma UI leve sobre estes mesmos scripts:

- Linux: TUI com `whiptail/dialog` ou app empacotado.
- Windows: wizard `.exe` chamando `install-las-platform.ps1`.

Mesmo com UI, a CLI permanece obrigatoria para automacao, auditoria e suporte remoto.
