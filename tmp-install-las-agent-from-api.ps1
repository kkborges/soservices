# LAS Plataforma de Monitoramento e Observabilidade
$ErrorActionPreference = "Stop"

$PLATFORM_URL = "https://api.soservices.com.br"
$AGENT_TOKEN = "nxa_4WxBMSbcWrxTh7otCqeVC9eEtKreYfG9a3xsgNTaiG9TTRwL"
$AGENT_ROLE = "agent"
$GATEWAY_URLS = "https://gw-shared-a.soservices.com.br,https://gw-shared-b.soservices.com.br,https://gw-shared-failover.soservices.com.br"
$INSTALL_DIR = "C:\LASAgent"
$CONFIG_DIR = "C:\LASAgent\config"
$LOG_DIR = "C:\LASAgent\logs"
$SERVICE_NAME = "LASAgent"
$EXPECTED_SHA256 = "4F3E5B8DCEE9EA327B1AF99E8E6A148F244C48A34E400E765F279A97FEC5093B"
$FINAL_EXE = "$INSTALL_DIR\las-agent.exe"

Write-Host "LAS Plataforma de Monitoramento e Observabilidade" -ForegroundColor Cyan
Write-Host "Instalador do agente Windows" -ForegroundColor Green

if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Execute o PowerShell como Administrador." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

Write-Progress -Activity "LAS Agent" -Status "Gravando configuracao" -PercentComplete 10
@"
[nexus]
nexus_url = https://api.soservices.com.br
agent_token = nxa_4WxBMSbcWrxTh7otCqeVC9eEtKreYfG9a3xsgNTaiG9TTRwL
role = agent
log_dir = C:\LASAgent\logs
install_dir = C:\LASAgent

[intervals]
heartbeat_interval = 60
metrics_interval = 30

[routing]
gateway_urls = https://gw-shared-a.soservices.com.br,https://gw-shared-b.soservices.com.br,https://gw-shared-failover.soservices.com.br
routing_refresh_interval = 300
gateway_strategy = priority-weighted-failover

[features]
process_monitor = true
port_scan = true
disk_monitor = true
network_monitor = true
log_collection = true
otel_enabled = true
ids_enabled = false
"@ | Set-Content -LiteralPath "$CONFIG_DIR\agent.conf" -Encoding Ascii

$headers = @{ "Authorization" = "Bearer $AGENT_TOKEN" }
$artifactTemp = Join-Path $env:TEMP ("las-agent-" + [guid]::NewGuid().ToString() + ".exe")

if (Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue) {
    Write-Progress -Activity "LAS Agent" -Status "Parando servico anterior" -PercentComplete 18
    Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Progress -Activity "LAS Agent" -Status "Baixando agente" -PercentComplete 30
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    & curl.exe -L --fail --progress-bar `
      -H "Authorization: Bearer $AGENT_TOKEN" `
      "$PLATFORM_URL/api/v1/agents/artifacts/windows-agent.exe" `
      -o $artifactTemp
} else {
    Invoke-WebRequest -Uri "$PLATFORM_URL/api/v1/agents/artifacts/windows-agent.exe" `
      -Headers $headers `
      -OutFile $artifactTemp
}

if (-not (Test-Path $artifactTemp)) {
    throw "Falha ao baixar o executavel do agente."
}

$artifactSize = (Get-Item $artifactTemp).Length
if ($artifactSize -lt 1MB) {
    throw "Executavel baixado com tamanho invalido: $artifactSize bytes"
}

if ($EXPECTED_SHA256) {
    $artifactHash = (Get-FileHash $artifactTemp -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($artifactHash -ne $EXPECTED_SHA256.ToUpperInvariant()) {
        throw "Hash do agente invalido. Esperado: $EXPECTED_SHA256 / Obtido: $artifactHash"
    }
}

if (Test-Path $FINAL_EXE) {
    Remove-Item -Force $FINAL_EXE -ErrorAction SilentlyContinue
}

Move-Item -Force $artifactTemp $FINAL_EXE
Unblock-File -Path $FINAL_EXE -ErrorAction SilentlyContinue

$nssmPath = "$INSTALL_DIR\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    Write-Progress -Activity "LAS Agent" -Status "Baixando NSSM" -PercentComplete 55
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\nssm.zip"
    Expand-Archive -Path "$env:TEMP\nssm.zip" -DestinationPath "$env:TEMP\nssm" -Force
    Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" $nssmPath -Force
}

Write-Progress -Activity "LAS Agent" -Status "Registrando servico" -PercentComplete 75
if (Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue) {
    & $nssmPath stop $SERVICE_NAME | Out-Null
    & $nssmPath remove $SERVICE_NAME confirm | Out-Null
}

& $nssmPath install $SERVICE_NAME $FINAL_EXE
& $nssmPath set $SERVICE_NAME AppDirectory $INSTALL_DIR
& $nssmPath set $SERVICE_NAME AppStdout "$LOG_DIR\agent.log"
& $nssmPath set $SERVICE_NAME AppStderr "$LOG_DIR\agent-error.log"
& $nssmPath set $SERVICE_NAME Start SERVICE_AUTO_START
& $nssmPath set $SERVICE_NAME AppEnvironmentExtra "NEXUS_CONFIG=$CONFIG_DIR\agent.conf"

Write-Progress -Activity "LAS Agent" -Status "Iniciando servico" -PercentComplete 90
Start-Service $SERVICE_NAME

$status = (Get-Service -Name $SERVICE_NAME).Status
Write-Progress -Activity "LAS Agent" -Completed
if ($status -eq "Running") {
    Write-Host "Agente instalado e em execucao." -ForegroundColor Green
    Write-Host "Token: nxa_4WxBMSbcWrxTh7otCqeVC9eEtKreYfG9a3xsgNTaiG9TTRwL" -ForegroundColor Yellow
    Write-Host "Plataforma: https://api.soservices.com.br" -ForegroundColor Cyan
    Write-Host "Config: $CONFIG_DIR\agent.conf" -ForegroundColor Cyan
    Write-Host "Logs: $LOG_DIR\agent.log" -ForegroundColor Cyan
} else {
    Write-Host "Falha ao iniciar o servico. Verifique os logs." -ForegroundColor Red
    exit 1
}

