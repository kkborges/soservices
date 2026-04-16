# LAS Validation Apps

Laboratorio minimo para gerar trafego real em tenants de validacao da LAS Plataforma.

## Servicos

- `.NET`: `http://localhost:5081`
- `Java`: `http://localhost:5082`
- `PHP/HTML`: `http://localhost:5083`

## Execucao

```bash
docker compose up -d --build
curl http://localhost:5081/health
curl http://localhost:5082/health
curl http://localhost:5083/health
```

## Uso no tenant de validacao

1. Instale o agente LAS na VM que executa este laboratorio.
2. Habilite `infra+otel` e coleta de logs no host.
3. Gere chamadas nos endpoints `/`, `/health` e `/work`.
4. Valide dados em `Hosts`, `Logs`, `Traces` e `Tickets`.

Estes apps nao contem dados mockados da plataforma. Eles apenas geram carga HTTP simples para teste real de monitoramento.
