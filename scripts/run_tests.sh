#!/bin/bash
# Script para executar testes corretamente no servidor Nexus

set -e

# Determine the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Activate virtual environment if exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Set PYTHONPATH to include backend directory
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"

# Change to backend directory for imports to work correctly
cd "$BACKEND_DIR"

# Run tests with proper path
echo "🧪 Running Nexus Tests..."
echo "📍 Project Root: $PROJECT_ROOT"
echo "📍 Backend Dir: $BACKEND_DIR"
echo "📍 PYTHONPATH: $PYTHONPATH"
echo ""

# Execute pytest with all arguments passed through
pytest "$@" ../tests/backend/

echo ""
echo "✅ Tests completed!"
