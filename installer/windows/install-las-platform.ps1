<#
LAS Platform Universal Installer (Windows)
Instala servidor, agente ou gateway a partir de um unico ponto de entrada.
#>

param(
  [ValidateSet("install","start","stop","status","uninstall")]
  [string]$Action = "install",

  [ValidateSet("server","agent","gateway")]
  [string]$Target = "server",

  [ValidateSet("saas","onprem")]
  [string]$Deployment = "onprem",

  [ValidateSet("compose","standalone","kubernetes")]
  [string]$Runtime = "compose",

  [string]$Bundle = "",
  [string]$InstallDir = "C:\LASPlatform",
  [string]$LicenseFile = "",
  [string]$LicenseKey = "",

  [string]$ApiUrl = "https://api.soservices.com.br",
  [string]$Username = "",
  [string]$Password = "",
  [ValidateSet("infra","complete")]
  [string]$Profile = "infra",
  [string]$Modules = "",
  [ValidateSet("agents","integrations","logs","security","control")]
  [string]$GatewayType = "agents",
  [string]$GatewayName = "",

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
    throw "Execute este script como Administrador."
  }
}

function Write-Section([string]$Text) {
  Write-Host ""
  Write-Host "=== $Text ===" -ForegroundColor Cyan
}

function Save-LicenseSnapshot {
  param([string]$Dir, [string]$File, [string]$Key)
  if (-not $Dir) { return }
  $licenseDir = Join-Path $Dir "license"
  New-Item -ItemType Directory -Force -Path $licenseDir | Out-Null
  $target = Join-Path $licenseDir "license.json"
  if ($File -and (Test-Path $File)) {
    Copy-Item $File $target -Force
  } elseif ($Key) {
    @{ license_key = $Key; source = "installer"; installed_at = (Get-Date).ToString("o") } |
      ConvertTo-Json -Depth 5 | Set-Content $target -Encoding UTF8
  }
}

function Test-LicenseModule {
  param([string]$File, [string]$Requested)
  if (-not $File -or -not $Requested) { return }
  if (-not (Test-Path $File)) { throw "License file nao encontrado: $File" }
  $data = Get-Content $File -Raw | ConvertFrom-Json
  $plan = "$($data.plan)".ToLower()
  if ($plan -eq "trial") { return }
  $allowed = @()
  if ($data.modules) { $allowed += $data.modules }
  if ($data.licenses) { $allowed += $data.licenses }
  if ($data.entitlements) {
    $data.entitlements.PSObject.Properties | Where-Object { $_.Value } | ForEach-Object { $allowed += $_.Name }
  }
  $allowed = $allowed | ForEach-Object { "$_".ToLower().Replace("-","_") }
  foreach ($m in ($Requested -split ",")) {
    $module = $m.Trim().ToLower().Replace("-","_")
    if (-not $module -or $module -eq "logs") { continue }
    if ($allowed -notcontains $module -and $allowed -notcontains "full") {
      throw "Modulo '$module' nao esta habilitado na licenca."
    }
  }
}

function Invoke-Login {
  param([string]$ApiUrl, [string]$Username, [string]$Password, [string]$SessionFile)
  if (-not $ApiUrl -or -not $Username -or -not $Password) {
    throw "-ApiUrl, -Username e -Password sao obrigatorios para instalar agent/gateway."
  }
  $body = @{ username = $Username; password = $Password } | ConvertTo-Json
  Invoke-WebRequest -Uri "$($ApiUrl.TrimEnd('/'))/api/v1/auth/login" `
    -Method POST -Body $body -ContentType "application/json" `
    -SessionVariable session | Out-Null
  return $session
}

function Install-RemoteAgent {
  $session = Invoke-Login -ApiUrl $ApiUrl -Username $Username -Password $Password
  $url = "$($ApiUrl.TrimEnd('/'))/api/v1/agents/download/windows?role=agent&format=ps1&profile=$Profile"
  if ($Modules) { $url = "$url&modules=$Modules" }
  $script = Join-Path $env:TEMP "install-las-agent.ps1"
  Write-Section "Baixando instalador do agente pela API"
  Invoke-WebRequest -Uri $url -WebSession $session -OutFile $script
  powershell -ExecutionPolicy Bypass -File $script
}

function Install-RemoteGateway {
  $session = Invoke-Login -ApiUrl $ApiUrl -Username $Username -Password $Password
  $url = "$($ApiUrl.TrimEnd('/'))/api/v1/agents/download/gateway/windows?format=ps1&gateway_type=$GatewayType"
  if ($GatewayName) { $url = "$url&name=$([uri]::EscapeDataString($GatewayName))" }
  $script = Join-Path $env:TEMP "install-las-gateway.ps1"
  Write-Section "Baixando instalador do gateway pela API"
  Invoke-WebRequest -Uri $url -WebSession $session -OutFile $script
  powershell -ExecutionPolicy Bypass -File $script
}

Assert-Admin

if ($Target -eq "server") {
  Save-LicenseSnapshot -Dir $InstallDir -File $LicenseFile -Key $LicenseKey
  if ($Runtime -eq "compose") {
    $script = Join-Path $PSScriptRoot "install-las-server.ps1"
    & $script -Action $Action -Bundle $Bundle -InstallDir $InstallDir -Mode $Deployment
    exit $LASTEXITCODE
  }
  if ($Runtime -eq "standalone") {
    $script = Join-Path $PSScriptRoot "install-las-server-standalone.ps1"
    & $script -Action $Action -Bundle $Bundle -InstallDir $InstallDir `
      -Postgres $Postgres -PostgresHost $PostgresHost -PostgresPort $PostgresPort `
      -PostgresDb $PostgresDb -PostgresUser $PostgresUser -PostgresPassword $PostgresPassword `
      -Redis $Redis -RedisHost $RedisHost -RedisPort $RedisPort -RedisDb $RedisDb `
      -RedisPassword $RedisPassword -Collector $Collector -OtelEndpoint $OtelEndpoint
    exit $LASTEXITCODE
  }
  if ($Runtime -eq "kubernetes") {
    Write-Host "Kubernetes: use o pacote k8s/helm do bundle."
    Write-Host "Comando sugerido: helm upgrade --install las-platform ./k8s/helm/las-platform -n las --create-namespace"
    exit 0
  }
}

if ($Target -eq "agent") {
  Test-LicenseModule -File $LicenseFile -Requested ($(if ($Modules) { $Modules } else { $Profile }))
  Install-RemoteAgent
  exit 0
}

if ($Target -eq "gateway") {
  Test-LicenseModule -File $LicenseFile -Requested $GatewayType
  Install-RemoteGateway
  exit 0
}
