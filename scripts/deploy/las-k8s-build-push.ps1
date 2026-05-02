param(
  [Parameter(Mandatory = $true)]
  [string]$Registry,

  [string]$Tag = "4.1.0",
  [string]$BackendImage = "las-backend-release",
  [string]$FrontendImage = "las-frontend",
  [string]$BackendDockerfile = "backend/Dockerfile.release",
  [string]$FrontendDockerfile = "frontend/Dockerfile",
  [switch]$NoPush
)

$ErrorActionPreference = "Stop"

function Join-Image([string]$Registry, [string]$Name, [string]$Tag) {
  return "$($Registry.TrimEnd('/'))/$($Name):$Tag"
}

$backendRef = Join-Image $Registry $BackendImage $Tag
$frontendRef = Join-Image $Registry $FrontendImage $Tag

Write-Host "[LAS K8S] Building backend: $backendRef" -ForegroundColor Cyan
docker build -t $backendRef -f $BackendDockerfile backend

Write-Host "[LAS K8S] Building frontend: $frontendRef" -ForegroundColor Cyan
docker build -t $frontendRef -f $FrontendDockerfile frontend

if (-not $NoPush) {
  Write-Host "[LAS K8S] Pushing backend..." -ForegroundColor Cyan
  docker push $backendRef
  Write-Host "[LAS K8S] Pushing frontend..." -ForegroundColor Cyan
  docker push $frontendRef
}

Write-Host ""
Write-Host "Use no Helm:" -ForegroundColor Green
Write-Host "  --set images.api.repository=$($Registry.TrimEnd('/'))/$BackendImage ``"
Write-Host "  --set images.api.tag=$Tag ``"
Write-Host "  --set images.frontend.repository=$($Registry.TrimEnd('/'))/$FrontendImage ``"
Write-Host "  --set images.frontend.tag=$Tag"
