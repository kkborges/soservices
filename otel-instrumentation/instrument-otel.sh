#!/bin/bash

################################################################################
#                                                                              #
#   ðŸš€ OpenTelemetry Auto-Instrumentador para LAS - Script Shell             #
#                                                                              #
#   Uso: ./instrument-otel.sh [--enable-rum=true|false] [--token=...] [...]  #
#                                                                              #
################################################################################

set -e

# ============================================================================
# CORES E ESTILOS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ============================================================================
# VARIÃVEIS GLOBAIS
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(pwd)"
ENABLE_RUM=false
LAS_TOKEN="${LAS_TOKEN:-lsa_SUBSTITUA_ESTE_TOKEN}"
LAS_ENDPOINT="${LAS_ENDPOINT:-https://api.soservices.com.br:8443/api/v1/ingest/otel}"
SERVICE_NAME="${SERVICE_NAME:-app}"
DEBUG_MODE=false

DETECTED_LANGUAGE=""
DETECTED_FRAMEWORK=""

# ============================================================================
# FUNÃ‡Ã•ES DE UTILITÃRIO
# ============================================================================

print_header() {
    clear
    echo -e "${CYAN}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
    echo -e "${CYAN}â•‘  ðŸš€ OpenTelemetry Auto-Instrumentador para LAS            â•‘${NC}"
    echo -e "${CYAN}â•‘     Script Shell - Auto-DetecÃ§Ã£o & Deploy                 â•‘${NC}"
    echo -e "${CYAN}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}â„¹ï¸  $1${NC}"
}

log_success() {
    echo -e "${GREEN}âœ“ $1${NC}"
}

log_error() {
    echo -e "${RED}âœ— $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}âš ï¸  $1${NC}"
}

print_separator() {
    echo -e "${CYAN}â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€${NC}"
}

# ============================================================================
# PARSER DE ARGUMENTOS
# ============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --enable-rum=true)
                ENABLE_RUM=true
                shift
                ;;
            --enable-rum=false)
                ENABLE_RUM=false
                shift
                ;;
            --enable-rum)
                ENABLE_RUM=true
                shift
                ;;
            --disable-rum)
                ENABLE_RUM=false
                shift
                ;;
            --token=*)
                LAS_TOKEN="${1#*=}"
                shift
                ;;
            --endpoint=*)
                LAS_ENDPOINT="${1#*=}"
                shift
                ;;
            --service-name=*)
                SERVICE_NAME="${1#*=}"
                shift
                ;;
            --debug)
                DEBUG_MODE=true
                shift
                ;;
            --help|-h)
                print_usage
                exit 0
                ;;
            *)
                log_error "Argumento desconhecido: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

print_usage() {
    cat << EOF

${BOLD}Uso: ./instrument-otel.sh [opÃ§Ãµes]${NC}

${BOLD}OpÃ§Ãµes:${NC}
  --enable-rum=true|false      Ativar/desativar RUM (padrÃ£o: false)
  --enable-rum                 Atalho para --enable-rum=true
  --disable-rum                Atalho para --enable-rum=false
  --token=TOKEN                Token LAS (padrÃ£o: env LAS_TOKEN)
  --endpoint=URL               Endpoint LAS (padrÃ£o: api.soservices.com.br)
  --service-name=NAME          Nome do serviÃ§o (padrÃ£o: app)
  --debug                      Modo debug
  --help                       Mostrar esta ajuda

${BOLD}Exemplos:${NC}
  ./instrument-otel.sh --enable-rum
  ./instrument-otel.sh --enable-rum=true --service-name=meu-app
  ./instrument-otel.sh --debug --disable-rum

EOF
}

# ============================================================================
# DETECÃ‡ÃƒO DE LINGUAGEM
# ============================================================================

detect_language() {
    log_info "ðŸ” Detectando linguagem do projeto..."
    
    # Python
    if [ -f "requirements.txt" ] || [ -f "setup.py" ] || [ -f "pyproject.toml" ] || [ -f "Pipfile" ]; then
        DETECTED_LANGUAGE="python"
        log_success "Linguagem detectada: ${BOLD}PYTHON${NC}"
        return 0
    fi
    
    # Node.js
    if [ -f "package.json" ]; then
        DETECTED_LANGUAGE="nodejs"
        log_success "Linguagem detectada: ${BOLD}NODE.JS${NC}"
        return 0
    fi
    
    # Java
    if [ -f "pom.xml" ] || [ -f "build.gradle" ] || [ -f "*.jar" ]; then
        DETECTED_LANGUAGE="java"
        log_success "Linguagem detectada: ${BOLD}JAVA${NC}"
        return 0
    fi
    
    # .NET
    if ls *.csproj >/dev/null 2>&1 || ls *.vbproj >/dev/null 2>&1 || [ -f "*.sln" ]; then
        DETECTED_LANGUAGE="dotnet"
        log_success "Linguagem detectada: ${BOLD}.NET${NC}"
        return 0
    fi
    
    # PHP
    if [ -f "composer.json" ] || [ -f "index.php" ]; then
        DETECTED_LANGUAGE="php"
        log_success "Linguagem detectada: ${BOLD}PHP${NC}"
        return 0
    fi
    
    log_error "Linguagem nÃ£o identificada"
    return 1
}

# ============================================================================
# DETECÃ‡ÃƒO DE FRAMEWORK
# ============================================================================

detect_framework() {
    log_info "ðŸ” Detectando framework..."
    
    case $DETECTED_LANGUAGE in
        python)
            if [ -f "requirements.txt" ]; then
                if grep -q "fastapi" requirements.txt; then
                    DETECTED_FRAMEWORK="fastapi"
                elif grep -q "django" requirements.txt; then
                    DETECTED_FRAMEWORK="django"
                elif grep -q "flask" requirements.txt; then
                    DETECTED_FRAMEWORK="flask"
                fi
            fi
            ;;
        nodejs)
            if [ -f "package.json" ]; then
                if grep -q "express" package.json; then
                    DETECTED_FRAMEWORK="express"
                elif grep -q "nestjs" package.json; then
                    DETECTED_FRAMEWORK="nestjs"
                elif grep -q "next" package.json; then
                    DETECTED_FRAMEWORK="next"
                fi
            fi
            ;;
        java)
            if grep -q "spring" pom.xml 2>/dev/null || grep -q "spring" build.gradle 2>/dev/null; then
                DETECTED_FRAMEWORK="spring"
            elif grep -q "quarkus" pom.xml 2>/dev/null || grep -q "quarkus" build.gradle 2>/dev/null; then
                DETECTED_FRAMEWORK="quarkus"
            fi
            ;;
    esac
    
    if [ -n "$DETECTED_FRAMEWORK" ]; then
        log_success "Framework detectado: ${BOLD}${DETECTED_FRAMEWORK}${NC}"
    else
        log_warning "Framework nÃ£o identificado (usando valores padrÃ£o)"
    fi
}

# ============================================================================
# CRIAR CONFIGURAÃ‡ÃƒO LAS
# ============================================================================

create_las_config() {
    log_info "ðŸ“ Criando arquivo de configuraÃ§Ã£o..."
    
    local config_file=".env"
    
    cat > "$config_file" << EOF
# ============================================================
# OpenTelemetry Configuration for LAS
# Auto-generated by instrument-otel.sh
# ============================================================

# LAS Platform
LAS_ENDPOINT=${LAS_ENDPOINT}
LAS_TOKEN=${LAS_TOKEN}

# Service Information
SERVICE_NAME=${SERVICE_NAME}
SERVICE_VERSION=1.0.0
SERVICE_ENVIRONMENT=production

# Instrumentation Options
ENABLE_RUM=$([ "$ENABLE_RUM" = true ] && echo "true" || echo "false")
ENABLE_METRICS=true
ENABLE_LOGS=true

# Tracing
TRACE_SAMPLE_RATE=1.0

# mTLS (optional)
MTLS_ENABLED=false
# MTLS_CERT_PATH=/path/to/client.crt
# MTLS_KEY_PATH=/path/to/client.key
# MTLS_CA_PATH=/path/to/ca.crt

# Proxy (optional)
# HTTP_PROXY=
# HTTPS_PROXY=

# Debug
DEBUG_MODE=$([ "$DEBUG_MODE" = true ] && echo "true" || echo "false")

# ============================================================
EOF
    
    log_success "Arquivo de configuraÃ§Ã£o criado: ${BOLD}${config_file}${NC}"
}

# ============================================================================
# INSTRUMENTAÃ‡ÃƒO POR LINGUAGEM
# ============================================================================

instrument_python() {
    log_info "ðŸ“¦ Instrumentando Python..."
    print_separator
    
    local req_file="requirements.txt"
    local otel_packages=(
        "opentelemetry-sdk>=1.20.0"
        "opentelemetry-exporter-otlp>=0.41b0"
        "opentelemetry-api>=1.20.0"
        "opentelemetry-sdk-resources>=0.41b0"
        "opentelemetry-instrumentation>=0.41b0"
    )
    
    # Adicionar pacotes especÃ­ficos do framework
    case $DETECTED_FRAMEWORK in
        fastapi)
            otel_packages+=("opentelemetry-instrumentation-fastapi>=0.41b0")
            ;;
        django)
            otel_packages+=("opentelemetry-instrumentation-django>=0.41b0")
            ;;
        flask)
            otel_packages+=("opentelemetry-instrumentation-flask>=0.41b0")
            ;;
    esac
    
    # Adicionar pacotes comuns
    otel_packages+=(
        "opentelemetry-instrumentation-requests>=0.41b0"
        "opentelemetry-instrumentation-psycopg2>=0.41b0"
    )
    
    # Atualizar requirements.txt
    if [ -f "$req_file" ]; then
        local backup="${req_file}.backup"
        cp "$req_file" "$backup"
        
        for package in "${otel_packages[@]}"; do
            local pkg_name="${package%%>=*}"
            if ! grep -q "$pkg_name" "$req_file"; then
                echo "$package" >> "$req_file"
                log_success "Adicionado: $pkg_name"
            fi
        done
    else
        log_warning "requirements.txt nÃ£o encontrado, criando..."
        for package in "${otel_packages[@]}"; do
            echo "$package" >> "$req_file"
        done
    fi
    
    # Copiar template de inicializaÃ§Ã£o
    if [ -f "${SCRIPT_DIR}/templates/python/otel_init.py" ]; then
        cp "${SCRIPT_DIR}/templates/python/otel_init.py" "./otel_init.py"
        log_success "Template criado: ${BOLD}otel_init.py${NC}"
    fi
    
    log_success "InstrumentaÃ§Ã£o Python concluÃ­da"
    print_separator
}

instrument_nodejs() {
    log_info "ðŸ“¦ Instrumentando Node.js..."
    print_separator
    
    if ! [ -f "package.json" ]; then
        log_error "package.json nÃ£o encontrado"
        return 1
    fi
    
    log_info "Instalando dependÃªncias OTel..."
    
    # Estrutura do npm install se necessÃ¡rio
    if ! command -v npm &> /dev/null; then
        log_error "npm nÃ£o encontrado. Instale Node.js primeiro."
        return 1
    fi
    
    # Adicionar pacotes OTel ao package.json (usando npm)
    npm install --save \
        @opentelemetry/sdk-node \
        @opentelemetry/auto-instrumentations-node \
        @opentelemetry/exporter-trace-otlp-http \
        @opentelemetry/api \
        @opentelemetry/sdk-trace-node
    
    log_success "Pacotes OTel instalados"
    
    # Copiar template
    if [ -f "${SCRIPT_DIR}/templates/nodejs/otel-init.js" ]; then
        cp "${SCRIPT_DIR}/templates/nodejs/otel-init.js" "./otel-init.js"
        log_success "Template criado: ${BOLD}otel-init.js${NC}"
    fi
    
    log_success "InstrumentaÃ§Ã£o Node.js concluÃ­da"
    print_separator
}

instrument_java() {
    log_info "ðŸ“¦ Instrumentando Java..."
    print_separator
    
    if [ -f "pom.xml" ]; then
        log_info "Detectado Maven (pom.xml)"
        log_warning "Adicione manualmente a dependÃªncia OTel em pom.xml"
    elif [ -f "build.gradle" ]; then
        log_info "Detectado Gradle (build.gradle)"
        log_warning "Adicione manualmente a dependÃªncia OTel em build.gradle"
    fi
    
    # Copiar classe de configuraÃ§Ã£o
    if [ -f "${SCRIPT_DIR}/templates/java/OTelConfig.java" ]; then
        mkdir -p "src/main/java/com/las"
        cp "${SCRIPT_DIR}/templates/java/OTelConfig.java" "src/main/java/com/las/OTelConfig.java"
        log_success "OTelConfig.java criado"
    fi
    
    print_separator
}

instrument_dotnet() {
    log_info "ðŸ“¦ Instrumentando .NET..."
    print_separator
    
    log_info "Instalando pacotes NuGet..."
    
    dotnet add package OpenTelemetry \
    dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol \
    dotnet add package OpenTelemetry.Instrumentation.AspNetCore \
    dotnet add package OpenTelemetry.Instrumentation.Http
    
    log_success "Pacotes NuGet instalados"
    
    # Copiar classe de configuraÃ§Ã£o
    if [ -f "${SCRIPT_DIR}/templates/dotnet/OTelConfig.cs" ]; then
        cp "${SCRIPT_DIR}/templates/dotnet/OTelConfig.cs" "./OTelConfig.cs"
        log_success "OTelConfig.cs criado"
    fi
    
    print_separator
}

instrument_php() {
    log_info "ðŸ“¦ Instrumentando PHP..."
    print_separator
    
    if ! [ -f "composer.json" ]; then
        log_error "composer.json nÃ£o encontrado"
        return 1
    fi
    
    log_info "Instalando dependÃªncias via Composer..."
    
    composer require open-telemetry/api open-telemetry/sdk open-telemetry/exporter-otlp
    
    log_success "Pacotes Composer instalados"
    
    # Copiar template
    if [ -f "${SCRIPT_DIR}/templates/php/otel-init.php" ]; then
        cp "${SCRIPT_DIR}/templates/php/otel-init.php" "./otel-init.php"
        log_success "Template criado: ${BOLD}otel-init.php${NC}"
    fi
    
    print_separator
}

# ============================================================================
# ADICIONAR RUM
# ============================================================================

add_rum() {
    if [ "$ENABLE_RUM" != true ]; then
        log_info "RUM nÃ£o foi habilitado (use --enable-rum)"
        return 0
    fi
    
    log_info "ðŸŽ¯ Adicionando Real User Monitoring..."
    print_separator
    
    mkdir -p "public"
    
    if [ -f "${SCRIPT_DIR}/rum/app.js" ]; then
        cp "${SCRIPT_DIR}/rum/app.js" "./public/app.js"
        log_success "RUM criado: ${BOLD}public/app.js${NC}"
        
        cat << 'EOF'

  ðŸ“ Para ativar RUM no seu HTML, adicione:

    <script src="/public/app.js"></script>

  Antes de </body>

EOF
    fi
    
    print_separator
}

# ============================================================================
# RESUMO E PRÃ“XIMOS PASSOS
# ============================================================================

print_summary() {
    print_separator
    echo ""
    echo -e "${BOLD}ðŸ“Š RESUMO DA INSTRUMENTAÃ‡ÃƒO${NC}"
    echo ""
    echo -e "  ${BLUE}Projeto:${NC} $PROJECT_DIR"
    echo -e "  ${BLUE}Linguagem:${NC} $DETECTED_LANGUAGE"
    [ -n "$DETECTED_FRAMEWORK" ] && echo -e "  ${BLUE}Framework:${NC} $DETECTED_FRAMEWORK"
    echo -e "  ${BLUE}RUM Habilitado:${NC} $([ "$ENABLE_RUM" = true ] && echo "âœ“ SIM" || echo "âœ— NÃƒO")"
    echo -e "  ${BLUE}Token LAS:${NC} ${LAS_TOKEN:0:20}..."
    echo ""
    print_separator
    
    echo ""
    echo -e "${BOLD}ðŸš€ PRÃ“XIMOS PASSOS:${NC}"
    echo ""
    
    case $DETECTED_LANGUAGE in
        python)
            echo "  1. Instalar dependÃªncias:"
            echo -e "     ${CYAN}pip install -r requirements.txt${NC}"
            echo ""
            echo "  2. Importar na sua aplicaÃ§Ã£o (no inÃ­cio do arquivo):"
            echo -e "     ${CYAN}import otel_init${NC}"
            echo ""
            echo "  3. Executar:"
            echo -e "     ${CYAN}python main.py${NC}"
            ;;
        nodejs)
            echo "  1. DependÃªncias jÃ¡ foram instaladas via npm"
            echo ""
            echo "  2. Importar na sua aplicaÃ§Ã£o (no inÃ­cio do arquivo):"
            echo -e "     ${CYAN}require('./otel-init.js');${NC}"
            echo ""
            echo "  3. Executar:"
            echo -e "     ${CYAN}npm start${NC}"
            ;;
        java)
            echo "  1. Adicionar dependÃªncia ao pom.xml ou build.gradle"
            echo ""
            echo "  2. @Import(OTelConfig.class) na sua classe"
            echo ""
            echo "  3. Build e execute"
            ;;
        dotnet)
            echo "  1. Pacotes NuGet foram instalados"
            echo ""
            echo "  2. Em Program.cs:"
            echo -e "     ${CYAN}builder.Services.AddLasOpenTelemetry();${NC}"
            echo ""
            echo "  3. Build e execute"
            ;;
        php)
            echo "  1. Composer instalou as dependÃªncias"
            echo ""
            echo "  2. No bootstrap da sua aplicaÃ§Ã£o:"
            echo -e "     ${CYAN}require_once __DIR__ . '/otel-init.php';${NC}"
            echo ""
            echo "  3. Execute sua aplicaÃ§Ã£o"
            ;;
    esac
    
    echo ""
    if [ "$ENABLE_RUM" = true ]; then
        echo "  âœ… RUM ativado - NÃ£o esqueÃ§a de adicionar o script no HTML"
    fi
    echo ""
    echo -e "${GREEN}âœ“ InstrumentaÃ§Ã£o concluÃ­da com sucesso!${NC}"
    echo ""
}

# ============================================================================
# FUNÃ‡ÃƒO PRINCIPAL
# ============================================================================

main() {
    print_header
    
    # Parsear argumentos
    parse_arguments "$@"
    
    echo ""
    log_info "Executando em: $PROJECT_DIR"
    echo ""
    
    # Detectar linguagem
    if ! detect_language; then
        print_separator
        log_error "Linguagem do projeto nÃ£o identificada"
        log_info "Verifique os arquivos de dependÃªncia do seu projeto"
        exit 1
    fi
    
    echo ""
    
    # Detectar framework
    detect_framework
    
    echo ""
    print_separator
    
    # Criar configuraÃ§Ã£o LAS
    echo ""
    create_las_config
    
    echo ""
    
    # Instrumentar por linguagem
    case $DETECTED_LANGUAGE in
        python)
            instrument_python
            ;;
        nodejs)
            instrument_nodejs
            ;;
        java)
            instrument_java
            ;;
        dotnet)
            instrument_dotnet
            ;;
        php)
            instrument_php
            ;;
        *)
            log_error "Linguagem nÃ£o suportada: $DETECTED_LANGUAGE"
            exit 1
            ;;
    esac
    
    # Adicionar RUM
    add_rum
    
    # Resumo
    print_summary
}

# ============================================================================
# EXECUTAR
# ============================================================================

main "$@"


