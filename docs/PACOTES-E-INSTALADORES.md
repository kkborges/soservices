# Pacotes, Instaladores e Cenários On-Premise

## Instaladores disponíveis

- Agente Linux: gerado em `https://las.soservices.com.br/api/v1/agents/download/linux`.
- Agente Windows: gerado em `https://las.soservices.com.br/api/v1/agents/download/windows`.
- Gateway Linux: gerado em `https://las.soservices.com.br/api/v1/agents/download/gateway/linux`.
- Gateway Windows: gerado em `https://las.soservices.com.br/api/v1/agents/download/gateway/windows`.
- Docker Compose do agente: `https://las.soservices.com.br/api/v1/agents/download/docker`.
- Manifesto Kubernetes: `https://las.soservices.com.br/api/v1/agents/download/k8s`.

Os downloads devem ser feitos com o usuário logado no tenant correto, porque cada arquivo recebe token e parâmetros específicos daquele tenant.

## Windows

- `LASAgentSetup.exe`: instalador principal do agente Windows.
- `LASGatewaySetup.exe`: instalador principal do gateway Windows.
- Ambos suportam instalação e desinstalação.
- Desinstalação silenciosa: `LASAgentSetup.exe /uninstall /quiet`.
- Desinstalação silenciosa: `LASGatewaySetup.exe /uninstall /quiet`.
- O download padrão pela interface Web entrega `Setup.exe`.
- O script PowerShell continua disponível como fallback em `/api/v1/agents/download/windows?format=ps1`.
- O script PowerShell do gateway continua disponível como fallback em `/api/v1/agents/download/gateway/windows?format=ps1`.

## Linux

- O instalador cria a configuração em `/etc/las/agent.conf` ou `/etc/las/gateway.conf`.
- O agente é instalado em `/opt/las`.
- O gateway é instalado em `/opt/las-gateway`.
- Os serviços systemd são `las-agent` e `las-gateway`.
- Logs do agente: `journalctl -u las-agent -f`.
- Logs do gateway: `journalctl -u las-gateway -f`.
- Desinstalação do agente: `sudo bash install-las-agent-linux.sh --uninstall`.
- Desinstalação do gateway: `sudo bash install-las-gateway-linux.sh --uninstall`.
- Limpeza também do arquivo de configuração: adicione `--purge`, por exemplo `sudo bash install-las-agent-linux.sh --uninstall --purge`.
- Por padrão, a desinstalação preserva logs e certificados para auditoria e evita remover arquivos compartilhados caso agente e gateway estejam no mesmo host.

## Comunicação segura

- Agentes e gateways usam `Authorization: Bearer <token>` apenas no bootstrap inicial.
- O bootstrap emite o bundle mTLS pela rota `https://api.soservices.com.br/api/v1/agents/bootstrap/mtls`.
- O tráfego operacional usa mTLS obrigatório no endpoint `https://api.soservices.com.br:8443`.
- Novos agentes e gateways são gerados com transporte protegido por padrão: `mTLS`, compressão habilitada e proteção de dados habilitada.
- Gateways recém-gerados aparecem como `pending_install` até o primeiro heartbeat real; depois passam para `online`, `stale` ou `offline`.
- O gateway recebe certificado de servidor próprio e publica `public_endpoint` em `https://<gateway>:9443`.
- O agente valida o certificado do gateway e usa certificado cliente no envio.
- Quando não existe gateway disponível para o tenant, o agente envia direto ao SaaS pela rota mTLS da plataforma.
- O instalador Windows valida o `SHA256` do payload antes de ativar o serviço.
- Ainda não existe criptografia adicional do payload acima do TLS/mTLS.
- O campo `encrypt_enabled` do gateway permanece reservado para uma camada futura de criptografia fim a fim no conteúdo.

## Rotas operacionais protegidas por mTLS

- `/api/v1/agents/routing`.
- `/api/v1/ingest/agent/*`.
- `/api/v1/ingest/gateway/*`.
- `/api/v1/ingest/logs`.
- `/api/v1/ingest/otel/*`.

## Operação em nuvem

- Containers Docker para frontend e backend.
- Banco PostgreSQL e Redis em serviço gerenciado ou stack HA.
- Instaladores gerados pela API.
- Gateway e agentes distribuídos conforme necessidade do tenant.

## Operação on-premise

- Imagem Docker ou pacote completo para o servidor principal.
- Gateway principal na mesma stack ou stack separada.
- Instaladores de agentes para Linux e Windows.
- TLS público ou certificado corporativo válido para os subdomínios do cliente.

## Próximos passos de empacotamento

- Manter `PyInstaller` para binários Linux/Windows.
- Avaliar `PyArmor` para obfuscação do código Python distribuído.
- Gerar imagem Docker versionada do servidor principal.
- Gerar imagem Docker versionada do gateway principal.
- Manter assinatura e versionamento dos artefatos liberados ao cliente.

## Atualizacao automatica

- A partir da versao `4.1.0`, agentes e gateways passam a consultar a plataforma periodicamente pela rota mTLS `/api/v1/agents/updates/check`.
- A plataforma responde a versao mais recente, artefato correto por sistema operacional e `SHA256` esperado.
- O componente baixa o novo payload somente quando houver versao diferente, valida o hash, troca o arquivo local e reinicia o processo ou servico.
- Linux usa substituicao atomica do script instalado e reinicio do proprio processo.
- Windows usa script auxiliar para parar o servico `LASAgent` ou `LASGateway`, substituir o `.exe` e iniciar novamente, evitando sobrescrever um executavel em uso.
- O primeiro salto a partir de instalacoes antigas `4.0.0` ainda exige reinstalacao ou atualizacao manual uma vez, porque essas versoes nao tinham cliente de autoupdate embutido.
- Depois do primeiro salto para `4.1.0`, correcoes e novas features podem ser distribuidas pelo fluxo de autoupdate.
