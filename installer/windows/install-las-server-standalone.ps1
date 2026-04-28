<#
LAS Server Standalone Setup (Windows, sem Docker)
- Instala a API (uvicorn) + Celery worker + Celery beat como servicos via NSSM
- Pode apontar para Postgres/Redis/Collector existentes (recomendado).
- Opcao de instalar localmente Postgres/Redis/Collector: tenta via Chocolatey (se presente) ou falha com instrucao.

Obs: Windows standalone requer Python instalado no host (py -3.11+).

Exemplos:
  .\\install-las-server-standalone.ps1 -Action install -Bundle .\\LAS_ONPREM_DEPLOY_20260424.tar.gz -InstallDir C:\\LASServerStandalone `
    -Postgres existing -PostgresHost 192.168.0.10 -PostgresUser las -PostgresPassword '***' -PostgresDb las `
    -Redis existing -RedisHost 192.168.0.11 -RedisPassword '***'

  .\\install-las-server-standalone.ps1 -Action status -InstallDir C:\\LASServerStandalone
#>

param(
  [ValidateSet("install","start","stop","status","uninstall")]
  [string]$Action = "install",

  [string]$Bundle = "",
  [string]$InstallDir = "C:\\LASServerStandalone",
  [string]$ListenHost = "0.0.0.0",
  [int]$ListenPort = 8000,

  [ValidateSet("existing","local")]
  [string]$Postgres = "existing",
  [string]$PostgresHost = "",
  [int]$PostgresPort = 5432,
  [string]$PostgresDb = "las",
  [string]$PostgresUser = "las",
  [string]$PostgresPassword = "",

  [ValidateSet("existing","local")]
  [string]$Redis = "existing",
  [string]$RedisHost = "",
  [int]$RedisPort = 6379,
  [int]$RedisDb = 0,
  [string]$RedisPassword = "",

  [ValidateSet("none","existing","local")]
  [string]$Collector = "none",
  [string]$OtelEndpoint = ""
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute como Administrador."
  }
}

function Write-Section([string]$text) {
  Write-Host ""
  Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Find-Python {
  if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  return $null
}

function Ensure-Nssm([string]$InstallDir) {
  $candidates = @(
    (Join-Path $PSScriptRoot "bin\\nssm.exe"),
    (Join-Path $InstallDir "nssm.exe")
  )
  foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
  throw "nssm.exe nao encontrado. Esperado em installer\\windows\\bin\\nssm.exe"
}

function Install-IfLocalDeps([string]$PostgresMode, [string]$RedisMode, [string]$CollectorMode) {
  $needs = @()
  if ($PostgresMode -eq "local") { $needs += "postgresql" }
  if ($RedisMode -eq "local") { $needs += "redis-64" }
  if ($CollectorMode -eq "local") { $needs += "opentelemetry-collector" }
  if ($needs.Count -eq 0) { return }

  if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    throw "Instalacao local de dependencias selecionada ($($needs -join ', ')), mas Chocolatey nao esta instalado. Instale dependencias manualmente ou use 'existing'."
  }
  Write-Section "Instalando dependencias locais via Chocolatey"
  foreach ($pkg in $needs) {
    & choco install $pkg -y | Out-Null
  }
}

Assert-Admin

$py = Find-Python
if (-not $py) { throw "Python nao encontrado. Instale Python 3.11+ ou habilite 'py'." }

Install-IfLocalDeps -PostgresMode $Postgres -RedisMode $Redis -CollectorMode $Collector

if ($Action -eq "install") {
  if (-not $Bundle) { throw "Informe -Bundle <LAS_*_DEPLOY_YYYYMMDD.tar.gz>." }
  if (-not (Test-Path $Bundle)) { throw "Bundle nao encontrado: $Bundle" }

  if ($Postgres -eq "existing" -and (-not $PostgresHost -or -not $PostgresPassword)) {
    throw "Postgres existing requer -PostgresHost e -PostgresPassword."
  }
  if ($Redis -eq "existing" -and (-not $RedisHost)) {
    throw "Redis existing requer -RedisHost."
  }

  Write-Section "Extraindo bundle"
  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  & tar.exe -xzf $Bundle -C $InstallDir
  $backendDir = Join-Path $InstallDir "backend"
  if (-not (Test-Path $backendDir)) { throw "Bundle nao contem backend/. Use LAS_*_DEPLOY." }

  Write-Section "Criando venv e instalando dependencias"
  $venvDir = Join-Path $InstallDir "venv"
  if (-not (Test-Path $venvDir)) {
    & $py -m venv $venvDir | Out-Null
  }
  $vpy = Join-Path $venvDir "Scripts\\python.exe"
  $pip = Join-Path $venvDir "Scripts\\pip.exe"
  & $pip install --upgrade pip wheel | Out-Null
  & $pip install -r (Join-Path $backendDir "requirements.txt") | Out-Null

  Write-Section "Gravando env"
  $env = @{
    "APP_HOST" = $ListenHost
    "APP_PORT" = "$ListenPort"
    "API_DOCS_ENABLED" = "true"
    "POSTGRES_HOST" = $PostgresHost
    "POSTGRES_PORT" = "$PostgresPort"
    "POSTGRES_DB" = $PostgresDb
    "POSTGRES_USER" = $PostgresUser
    "POSTGRES_PASSWORD" = $PostgresPassword
    "REDIS_HOST" = $RedisHost
    "REDIS_PORT" = "$RedisPort"
    "REDIS_DB" = "$RedisDb"
    "REDIS_PASSWORD" = $RedisPassword
    "OTEL_EXPORTER_OTLP_ENDPOINT" = $OtelEndpoint
  }
  # NSSM aceita multiplas variaveis em uma string com quebras de linha.
  $envExtra = ($env.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "`n"

  Write-Section "Registrando servicos (NSSM)"
  $nssm = Ensure-Nssm -InstallDir $InstallDir
  Copy-Item $nssm (Join-Path $InstallDir "nssm.exe") -Force
  $nssm = (Join-Path $InstallDir "nssm.exe")

  $apiSvc = "LASAPI"
  $workerSvc = "LASWorker"
  $beatSvc = "LASBeat"

  foreach ($svc in @($apiSvc,$workerSvc,$beatSvc)) {
    & $nssm stop $svc 2>$null | Out-Null
    & $nssm remove $svc confirm 2>$null | Out-Null
  }

  # API
  & $nssm install $apiSvc $vpy | Out-Null
  & $nssm set $apiSvc AppDirectory $backendDir | Out-Null
  & $nssm set $apiSvc AppParameters "-m uvicorn app.main:app --host $ListenHost --port $ListenPort" | Out-Null
  & $nssm set $apiSvc AppEnvironmentExtra $envExtra | Out-Null

  # Worker
  & $nssm install $workerSvc $vpy | Out-Null
  & $nssm set $workerSvc AppDirectory $backendDir | Out-Null
  & $nssm set $workerSvc AppParameters "-m celery -A app.workers.celery_app.celery_app worker -l info --concurrency=2 -Q ai,synthetic,security,collector,baseline,alerts,celery" | Out-Null
  & $nssm set $workerSvc AppEnvironmentExtra $envExtra | Out-Null

  # Beat
  & $nssm install $beatSvc $vpy | Out-Null
  & $nssm set $beatSvc AppDirectory $backendDir | Out-Null
  & $nssm set $beatSvc AppParameters "-m celery -A app.workers.celery_app.celery_app beat -l info" | Out-Null
  & $nssm set $beatSvc AppEnvironmentExtra $envExtra | Out-Null

  Write-Section "Iniciando servicos"
  & $nssm start $apiSvc | Out-Null
  & $nssm start $workerSvc | Out-Null
  & $nssm start $beatSvc | Out-Null

  Write-Host "Instalacao concluida. Health: http://$ListenHost`:$ListenPort/api/health" -ForegroundColor Green
  exit 0
}

if ($Action -eq "status") {
  $nssm = Ensure-Nssm -InstallDir $InstallDir
  foreach ($svc in @("LASAPI","LASWorker","LASBeat")) {
    & $nssm status $svc 2>$null
  }
  exit 0
}

if ($Action -eq "start") {
  $nssm = Ensure-Nssm -InstallDir $InstallDir
  foreach ($svc in @("LASAPI","LASWorker","LASBeat")) {
    & $nssm start $svc 2>$null | Out-Null
  }
  exit 0
}

if ($Action -eq "stop") {
  $nssm = Ensure-Nssm -InstallDir $InstallDir
  foreach ($svc in @("LASAPI","LASWorker","LASBeat")) {
    & $nssm stop $svc 2>$null | Out-Null
  }
  exit 0
}

if ($Action -eq "uninstall") {
  $nssm = Ensure-Nssm -InstallDir $InstallDir
  foreach ($svc in @("LASAPI","LASWorker","LASBeat")) {
    & $nssm stop $svc 2>$null | Out-Null
    & $nssm remove $svc confirm 2>$null | Out-Null
  }
  Remove-Item -Recurse -Force $InstallDir
  Write-Host "Desinstalacao concluida." -ForegroundColor Green
  exit 0
}
