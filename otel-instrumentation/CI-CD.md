# ðŸš€ IntegraÃ§Ã£o em CI/CD

Integre a instrumentaÃ§Ã£o OpenTelemetry em seu pipeline de deployment.

## ðŸ”„ GitHub Actions

### Arquivo: `.github/workflows/instrument-on-deploy.yml`

```yaml
name: Auto-Instrument OTel

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  instrument:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Create LAS config
        run: |
          cat > las-config.example.env << EOF
          LAS_TOKEN=${{ secrets.LAS_TOKEN }}
          LAS_ENDPOINT=${{ secrets.LAS_ENDPOINT }}
          SERVICE_NAME=${{ github.event.repository.name }}
          SERVICE_VERSION=${{ github.sha }}
          SERVICE_ENVIRONMENT=${{ github.ref_name }}
          DEBUG_MODE=false
          ENABLE_RUM=true
          EOF
      
      - name: Install dependencies
        run: |
          pip install python-dotenv
          pip install -r requirements.txt 2>/dev/null || echo "No requirements.txt"
      
      - name: Instrument application
        run: |
          python otel-instrumentation/instrument.py . --enable-rum
      
      - name: Verify instrumentation
        run: |
          if grep -q "opentelemetry" requirements.txt 2>/dev/null; then
            echo "âœ“ Python instrumentation successful"
          fi
          if grep -q "@opentelemetry" package.json 2>/dev/null; then
            echo "âœ“ Node.js instrumentation successful"
          fi
      
      - name: Commit changes
        run: |
          git config user.name "OTel Bot"
          git config user.email "otel@LAS.local"
          git add requirements.txt package.json otel_init.* 2>/dev/null
          git commit -m "chore: auto-instrument OpenTelemetry" || echo "No changes to commit"
      
      - name: Push to branch
        run: |
          git push origin HEAD:${{ github.ref_name }} || echo "No changes to push"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## ðŸ³ Docker Build

### Multi-stage build com OTel

```dockerfile
# Stage 1: InstrumentaÃ§Ã£o
FROM python:3.11 as instrumenter
WORKDIR /build
COPY otel-instrumentation ./otel-instrumentation
COPY requirements.txt .
COPY las-config.example.env .
RUN pip install python-dotenv
RUN python otel-instrumentation/instrument.py . --enable-rum

# Stage 2: AplicaÃ§Ã£o
FROM python:3.11
WORKDIR /app

# Copiar configuraÃ§Ã£o LAS
COPY --from=instrumenter /build/las-config.example.env .

# Copiar requirements atualizado com OTel
COPY --from=instrumenter /build/requirements.txt .

# Instalar
RUN pip install --no-cache-dir -r requirements.txt

# Copiar app
COPY . .

# Inicializar OTel
RUN echo "import otel_init" > /app/00-init.py

ENV PYTHONPATH=/app:$PYTHONPATH
ENV LAS_ENDPOINT=https://api.soservices.com.br:8443/api/v1/ingest/otel

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0"]
```

---

## ðŸš€ GitLab CI

### Arquivo: `.gitlab-ci.yml`

```yaml
stages:
  - instrument
  - build
  - deploy

instrument:
  stage: instrument
  image: python:3.11
  script:
    - pip install python-dotenv
    - |
      cat > las-config.example.env << EOF
      LAS_TOKEN=$LAS_TOKEN
      LAS_ENDPOINT=$LAS_ENDPOINT
      SERVICE_NAME=$CI_PROJECT_NAME
      SERVICE_VERSION=$CI_COMMIT_SHA
      SERVICE_ENVIRONMENT=$CI_COMMIT_BRANCH
      DEBUG_MODE=false
      ENABLE_RUM=true
      EOF
    - python otel-instrumentation/instrument.py . --enable-rum
  artifacts:
    paths:
      - requirements.txt
      - package.json
      - otel_init.*
  before_script:
    - pip install -r requirements.txt 2>/dev/null || true

build:
  stage: build
  image: docker:latest
  needs: ["instrument"]
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  image: bitnami/kubectl:latest
  needs: ["build"]
  script:
    - kubectl set image deployment/app app=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - kubectl rollout status deployment/app
  environment:
    name: production
    url: https://app.example.com
```

---

## ðŸ™ GitHub Actions - Node.js

```yaml
name: Node Instrument & Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Create LAS config
        run: |
          echo "LAS_TOKEN=${{ secrets.LAS_TOKEN }}" > .env
          echo "SERVICE_NAME=my-app" >> .env
          echo "ENABLE_RUM=true" >> .env
      
      - name: Install & Instrument
        run: |
          python otel-instrumentation/instrument.py . --enable-rum
          npm install
      
      - name: Build
        run: npm run build
      
      - name: Deploy to production
        run: npm run deploy
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
```

---

## ðŸ” Secrets & Variables

### GitHub

```bash
# Adicionar secrets
gh secret set LAS_TOKEN --body "lsa_SUBSTITUA_ESTE_TOKEN"
gh secret set LAS_ENDPOINT --body "https://api.soservices.com.br:8443/api/v1/ingest/otel"
```

### GitLab

```yaml
# Em Settings â†’ CI/CD â†’ Variables
LAS_TOKEN: lsa_SUBSTITUA_ESTE_TOKEN
LAS_ENDPOINT: https://api.soservices.com.br:8443/api/v1/ingest/otel
```

### Azure DevOps

```yaml
variables:
  LAS_TOKEN: $(nexusToken)
  LAS_ENDPOINT: https://api.soservices.com.br:8443/api/v1/ingest/otel
```

---

## ðŸ“¦ Kubernetes

### Secret para mTLS

```bash
kubectl create secret tls LAS-mtls \
  --cert=client.crt \
  --key=client.key \
  -n production
```

### ConfigMap para OTel

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-config
  namespace: production
data:
  las-config.example.env: |
    LAS_TOKEN=lsa_SUBSTITUA_ESTE_TOKEN
    LAS_ENDPOINT=https://api.soservices.com.br:8443/api/v1/ingest/otel
    SERVICE_NAME=my-app
    ENABLE_RUM=true
    MTLS_ENABLED=true
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:latest
        envFrom:
          - configMapRef:
              name: otel-config
        volumeMounts:
          - name: certificates
            mountPath: /etc/certs
            readOnly: true
        env:
          - name: MTLS_CERT_PATH
            value: /etc/certs/tls.crt
          - name: MTLS_KEY_PATH
            value: /etc/certs/tls.key
      volumes:
        - name: certificates
          secret:
            secretName: LAS-mtls
```

---

## ðŸ”„ Terraform

```hcl
# VariÃ¡veis
variable "LAS_TOKEN" {
  sensitive = true
}

variable "LAS_ENDPOINT" {
  default = "https://api.soservices.com.br:8443/api/v1/ingest/otel"
}

# Criar ConfigMap
resource "kubernetes_config_map" "otel" {
  metadata {
    name      = "otel-config"
    namespace = kubernetes_namespace.production.metadata[0].name
  }

  data = {
    "las-config.example.env" = templatefile("${path.module}/LAS-config.tpl", {
      token    = var.LAS_TOKEN
      endpoint = var.LAS_ENDPOINT
      service  = terraform.workspace
    })
  }
}

# Criar Secret para mTLS
resource "kubernetes_secret" "mtls" {
  metadata {
    name      = "LAS-mtls"
    namespace = kubernetes_namespace.production.metadata[0].name
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = file("${path.module}/certs/client.crt")
    "tls.key" = file("${path.module}/certs/client.key")
  }
}
```

---

## ðŸš€ Ansible

```yaml
---
- name: Deploy app with OTel
  hosts: production
  tasks:
    - name: Create LAS config
      copy:
        dest: /etc/app/las-config.example.env
        content: |
          LAS_TOKEN={{ LAS_TOKEN }}
          LAS_ENDPOINT={{ LAS_ENDPOINT }}
          SERVICE_NAME=my-app
          ENABLE_RUM=true

    - name: Instrument application
      command: python otel-instrumentation/instrument.py . --enable-rum
      args:
        chdir: /opt/app

    - name: Restart service
      systemd:
        name: app
        state: restarted
        daemon_reload: true
```

---

## ðŸ“Š Monitoramento do Pipeline

### Verificar se instrumentaÃ§Ã£o foi bem-sucedida

```bash
#!/bin/bash

# Checker script
check_instrumentation() {
    local project_dir=$1
    
    echo "ðŸ” Verificando instrumentaÃ§Ã£o..."
    
    # Python
    if [ -f "$project_dir/requirements.txt" ]; then
        if grep -q "opentelemetry" "$project_dir/requirements.txt"; then
            echo "âœ“ Python: OTel adicionado"
        else
            echo "âœ— Python: OTel NÃƒO adicionado"
            return 1
        fi
    fi
    
    # Node.js
    if [ -f "$project_dir/package.json" ]; then
        if grep -q "@opentelemetry" "$project_dir/package.json"; then
            echo "âœ“ Node.js: OTel adicionado"
        else
            echo "âœ— Node.js: OTel NÃƒO adicionado"
            return 1
        fi
    fi
    
    # Arquivo de init
    if [ -f "$project_dir/otel_init.py" ] || [ -f "$project_dir/otel-init.js" ]; then
        echo "âœ“ Arquivo de inicializaÃ§Ã£o criado"
    else
        echo "âœ— Arquivo de inicializaÃ§Ã£o NÃƒO encontrado"
        return 1
    fi
    
    echo "âœ“ InstrumentaÃ§Ã£o OK"
    return 0
}

check_instrumentation $(pwd)
```

---

## ðŸŽ¯ Best Practices

1. **Secrets**
   - Nunca commitar tokens em cÃ³digo
   - Usar CI/CD secrets management

2. **Staging**
   - Testar instrumentaÃ§Ã£o em staging first
   - Verificar impacto de performance

3. **Rollback**
   - Manter branches sem OTel para rollback rÃ¡pido
   - Usar feature flags se necessÃ¡rio

4. **Monitoramento**
   - Monitorar volume de traces
   - Ajustar sampling rate conforme necessÃ¡rio

5. **DocumentaÃ§Ã£o**
   - Documentar configuraÃ§Ã£o por ambiente
   - Manter runbook de troubleshooting

---

**Pronto para automatizar sua instrumentaÃ§Ã£o!** ðŸš€


