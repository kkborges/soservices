# LAS Plataforma de Monitoramento e Observabilidade
$ErrorActionPreference = "Stop"

$PLATFORM_URL = "http://localhost:8000"
$AGENT_TOKEN = "tok_test"
$AGENT_ROLE = "agent"
$GATEWAY_URLS = "http://10.0.0.10:8080"
$INSTALL_DIR = "C:\LASAgent"
$CONFIG_DIR = "C:\LASAgent\config"
$LOG_DIR = "C:\LASAgent\logs"
$SERVICE_NAME = "LASAgent"

Write-Host "LAS Plataforma de Monitoramento e Observabilidade" -ForegroundColor Cyan
Write-Host "Instalador do agente Windows" -ForegroundColor Green

if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Execute o PowerShell como Administrador." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

@"
[nexus]
nexus_url = http://localhost:8000
agent_token = tok_test
role = agent
log_dir = C:\LASAgent\logs
install_dir = C:\LASAgent

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[routing]
gateway_urls = http://10.0.0.10:8080

[features]
process_monitor = true
port_scan = true
disk_monitor = true
network_monitor = true
log_collection = true
otel_enabled = true
ids_enabled = false
"@ | Set-Content -LiteralPath "$CONFIG_DIR\agent.conf" -Encoding UTF8

$headers = @{ "Authorization" = "Bearer $AGENT_TOKEN" }
Invoke-WebRequest -Uri "$PLATFORM_URL/api/v1/agents/artifacts/windows-agent.py" `
  -Headers $headers `
  -OutFile "$INSTALL_DIR\las-agent.py"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    Write-Host "Python nao encontrado. Instalando Python 3.12..." -ForegroundColor Yellow
    $pythonInstaller = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe" -OutFile $pythonInstaller
    Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}

if (-not $pythonCommand) {
    Write-Host "Python nao foi localizado apos a instalacao." -ForegroundColor Red
    exit 1
}

$pythonPath = $pythonCommand.Source
& $pythonPath -m pip install -q --upgrade pip
& $pythonPath -m pip install -q psutil requests

$nssmPath = "$INSTALL_DIR\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\nssm.zip"
    Expand-Archive -Path "$env:TEMP\nssm.zip" -DestinationPath "$env:TEMP\nssm" -Force
    Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" $nssmPath -Force
}

& $nssmPath install $SERVICE_NAME $pythonPath "$INSTALL_DIR\las-agent.py"
& $nssmPath set $SERVICE_NAME AppDirectory $INSTALL_DIR
& $nssmPath set $SERVICE_NAME AppStdout "$LOG_DIR\agent.log"
& $nssmPath set $SERVICE_NAME AppStderr "$LOG_DIR\agent-error.log"
& $nssmPath set $SERVICE_NAME Start SERVICE_AUTO_START
& $nssmPath set $SERVICE_NAME AppEnvironmentExtra "NEXUS_CONFIG=$CONFIG_DIR\agent.conf"

Start-Service $SERVICE_NAME

$status = (Get-Service -Name $SERVICE_NAME).Status
if ($status -eq "Running") {
    Write-Host "Agente instalado e em execucao." -ForegroundColor Green
    Write-Host "Token: tok_test" -ForegroundColor Yellow
    Write-Host "Plataforma: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Config: $CONFIG_DIR\agent.conf" -ForegroundColor Cyan
    Write-Host "Logs: $LOG_DIR\agent.log" -ForegroundColor Cyan
} else {
    Write-Host "Falha ao iniciar o servico. Verifique os logs." -ForegroundColor Red
    exit 1
}
