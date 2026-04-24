$ErrorActionPreference = "Stop"

function Write-Section($text) {
  Write-Host ""
  Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script como Administrador."
  }
}

function Get-ComposeCommand {
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) { return "docker-compose" }
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
      docker compose version | Out-Null
      return "docker compose"
    } catch {}
  }
  return $null
}

param(
  [ValidateSet("install","start","stop","status","uninstall")]
  [string]$Action = "install",
  [string]$Bundle = "",
  [string]$InstallDir = "C:\\LASServer",
  [ValidateSet("onprem","saas")]
  [string]$Mode = "onprem",
  [switch]$PurgeVolumes
)

Assert-Admin
$compose = Get-ComposeCommand
if (-not $compose) { throw "Docker Compose nao encontrado. Instale Docker + docker-compose (ou docker compose)." }

$dockerDir = Join-Path $InstallDir "docker"
$composeFile = if ($Mode -eq "saas") { "docker-compose.ha.release.yml" } else { "docker-compose.onprem-ha.release.yml" }

function Resolve-ComposeFile {
  if (Test-Path (Join-Path $dockerDir $composeFile)) { return $composeFile }
  if ($Mode -eq "saas" -and (Test-Path (Join-Path $dockerDir "docker-compose.ha.yml"))) { return "docker-compose.ha.yml" }
  if ($Mode -ne "saas" -and (Test-Path (Join-Path $dockerDir "docker-compose.onprem-ha.yml"))) { return "docker-compose.onprem-ha.yml" }
  throw "Compose file nao encontrado em $dockerDir"
}

function Invoke-Compose([string]$cmd, [string]$file, [string[]]$args) {
  Push-Location $dockerDir
  try {
    if ($cmd -eq "docker-compose") {
      & docker-compose -f $file @args
    } else {
      & docker compose -f $file @args
    }
  } finally {
    Pop-Location
  }
}

if ($Action -eq "install") {
  if (-not $Bundle) { throw "Informe -Bundle <LAS_*_DEPLOY_YYYYMMDD.tar.gz>." }
  if (-not (Test-Path $Bundle)) { throw "Bundle nao encontrado: $Bundle" }

  Write-Section "Extraindo bundle"
  New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
  # Windows 10/11 normalmente tem tar.exe
  & tar.exe -xzf $Bundle -C $InstallDir

  if (-not (Test-Path $dockerDir)) { throw "Pasta docker nao encontrada apos extracao: $dockerDir" }

  # cria .env se nao existir
  $envExample = if ($Mode -eq "onprem") { Join-Path $dockerDir ".env.onprem.example" } else { Join-Path $dockerDir ".env.example" }
  $envTarget = Join-Path $dockerDir ".env"
  if ((Test-Path $envExample) -and (-not (Test-Path $envTarget))) {
    Copy-Item $envExample $envTarget -Force
    Write-Host "Criado $envTarget a partir de $envExample (ajuste conforme necessario)" -ForegroundColor Yellow
  }

  $f = Resolve-ComposeFile
  Write-Section "Subindo stack"
  Invoke-Compose $compose $f @("up","-d")
  Write-Host "Instalacao concluida em $InstallDir" -ForegroundColor Green
  exit 0
}

if ($Action -eq "start") {
  $f = Resolve-ComposeFile
  Invoke-Compose $compose $f @("up","-d")
  exit 0
}

if ($Action -eq "stop") {
  $f = Resolve-ComposeFile
  Invoke-Compose $compose $f @("down")
  exit 0
}

if ($Action -eq "status") {
  $f = Resolve-ComposeFile
  Invoke-Compose $compose $f @("ps")
  exit 0
}

if ($Action -eq "uninstall") {
  if (Test-Path $dockerDir) {
    $f = Resolve-ComposeFile
    if ($PurgeVolumes) {
      Invoke-Compose $compose $f @("down","-v")
    } else {
      Invoke-Compose $compose $f @("down")
    }
  }
  Remove-Item -Recurse -Force $InstallDir
  Write-Host "Desinstalacao concluida." -ForegroundColor Green
  exit 0
}

