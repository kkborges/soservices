$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $root
$script = Join-Path $PSScriptRoot "las_setup_bootstrap.py"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name LASAgentSetup `
  $script

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name LASGatewaySetup `
  $script

Copy-Item (Join-Path $repo "dist\\LASAgentSetup.exe") (Join-Path $repo "backend\\releases\\LASAgentSetup.exe") -Force
Copy-Item (Join-Path $repo "dist\\LASGatewaySetup.exe") (Join-Path $repo "backend\\releases\\LASGatewaySetup.exe") -Force

Write-Host "Setup executables generated in backend\\releases" -ForegroundColor Green
