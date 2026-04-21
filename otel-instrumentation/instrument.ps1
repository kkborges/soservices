# Script PowerShell para Auto-InstrumentaÃ§Ã£o
# Uso: .\instrument.ps1 -ProjectPath "." -EnableRUM $true

param(
    [string]$ProjectPath = ".",
    [bool]$EnableRUM = $true,
    [switch]$DisableRUM
)

if ($DisableRUM) {
    $EnableRUM = $false
}

Write-Host ""
Write-Host "â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—" -ForegroundColor Cyan
Write-Host "â•‘   OpenTelemetry Auto-Instrumentador        â•‘" -ForegroundColor Cyan
Write-Host "â•‘   para LAS (PowerShell)                  â•‘" -ForegroundColor Cyan
Write-Host "â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•" -ForegroundColor Cyan
Write-Host ""

# Verificar se Python estÃ¡ instalado
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "âœ— Python nÃ£o encontrado. Instale Python 3.8+ primeiro." -ForegroundColor Red
    exit 1
}

# Instalar dependÃªncias
Write-Host "ðŸ“¦ Instalando dependÃªncias..." -ForegroundColor Blue
python -m pip install python-dotenv | Out-Null

# Executar instrumentaÃ§Ã£o
Write-Host ""
Write-Host "ðŸ“ Projeto: $ProjectPath" -ForegroundColor Blue
Write-Host "ðŸŽ¯ RUM: $EnableRUM" -ForegroundColor Blue
Write-Host ""

if ($EnableRUM) {
    & python instrument.py $ProjectPath --enable-rum
} else {
    & python instrument.py $ProjectPath --disable-rum
}

