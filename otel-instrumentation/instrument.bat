@echo off
REM Script de Auto-InstrumentaÃ§Ã£o para Windows
REM Uso: instrument.bat [caminho] [--enable-rum|--disable-rum]

setlocal enabledelayedexpansion

REM ConfiguraÃ§Ã£o padrÃ£o
set PROJECT_PATH=.
set ENABLE_RUM=true

REM Processar argumentos
if not "%1"=="" set PROJECT_PATH=%1
if "%2"=="--disable-rum" set ENABLE_RUM=false

echo.
echo â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
echo â•‘   OpenTelemetry Auto-Instrumentador        â•‘
echo â•‘   para LAS (Windows)                     â•‘
echo â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
echo.

REM Verificar se Python estÃ¡ instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo âœ— Python nÃ£o encontrado. Instale Python 3.8+ primeiro.
    exit /b 1
)

REM Instalar dependÃªncias do script
echo ðŸ“¦ Instalando dependÃªncias...
pip install python-dotenv >nul 2>&1

REM Executar instrumentaÃ§Ã£o
echo.
echo ðŸ“ Projeto: %PROJECT_PATH%
echo ðŸŽ¯ RUM: %ENABLE_RUM%
echo.

if %ENABLE_RUM%==true (
    python instrument.py %PROJECT_PATH% --enable-rum
) else (
    python instrument.py %PROJECT_PATH% --disable-rum
)

endlocal

