#!/bin/bash
# Script de Auto-InstrumentaÃ§Ã£o para Linux/Mac
# Uso: ./instrument.sh [caminho] [--enable-rum|--disable-rum]

set -e

# ConfiguraÃ§Ã£o padrÃ£o
PROJECT_PATH="."
ENABLE_RUM="true"

# Processar argumentos
if [ -n "$1" ]; then
    PROJECT_PATH="$1"
fi

if [ "$2" = "--disable-rum" ]; then
    ENABLE_RUM="false"
fi

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—"
echo "â•‘   OpenTelemetry Auto-Instrumentador        â•‘"
echo "â•‘   para LAS (Linux/Mac)                   â•‘"
echo "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•"
echo ""

# Verificar se Python estÃ¡ instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}âœ— Python 3 nÃ£o encontrado. Instale Python 3.8+ primeiro.${NC}"
    exit 1
fi

# Instalar dependÃªncias
echo -e "${BLUE}ðŸ“¦ Instalando dependÃªncias...${NC}"
python3 -m pip install python-dotenv > /dev/null 2>&1

# Executar instrumentaÃ§Ã£o
echo ""
echo -e "${BLUE}ðŸ“ Projeto: $PROJECT_PATH${NC}"
echo -e "${BLUE}ðŸŽ¯ RUM: $ENABLE_RUM${NC}"
echo ""

if [ "$ENABLE_RUM" = "true" ]; then
    python3 instrument.py "$PROJECT_PATH" --enable-rum
else
    python3 instrument.py "$PROJECT_PATH" --disable-rum
fi

