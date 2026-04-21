# Estrutura Recomendada no Servidor (`/srv/las-plataforma`)

Este documento padroniza a estrutura de pastas solicitada para testes e implantacoes (SaaS e on-prem).

## Estrutura

Crie a pasta base:

```bash
sudo mkdir -p /srv/las-plataforma
sudo chown -R $USER:$USER /srv/las-plataforma
```

Dentro dela:

- `deploy-orquestracao/`
  Arquivos e manifests para implantacao via Docker/Kubernetes.
- `deploy-onpremise/`
  Versao on-prem com HA (no minimo 2 instancias da API) e stack auxiliar (Postgres/Redis).
- `fontes-instaladores/`
  Artefatos/instaladores para distribuicao: agentes/gateways (Linux/Windows) e pacotes auxiliares.

Exemplo:

```text
/srv/las-plataforma
  deploy-orquestracao/
    docker/
      docker-compose.yml
      docker-compose.proxy-manager.yml
      docker-compose.ha.yml
      docker-compose.mtls.yml
  deploy-onpremise/
    docker/
      docker-compose.data-ha.yml
      docker-compose.ha.yml
      docker-compose.mtls.yml
      docker-compose.proxy-manager.yml
  fontes-instaladores/
    releases/
      LASAgentSetup.exe
      LASGatewaySetup.exe
      las-agent-linux-x64.bin
      las-gateway-linux-x64.bin
```

Observacao:

- A pasta `fontes-instaladores` pode ser publicada em um endpoint interno (gateway do tenant) para downloads locais.
- Em ambiente SaaS, os downloads ficam disponiveis via `/api/v1/agents/download/...` (com tokens e licencas do tenant).

