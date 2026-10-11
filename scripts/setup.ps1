# One-time local setup on Windows PowerShell.
# Creates .venv, installs dependencies, and creates .env from .env.example if missing.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$pyVersion = (python -c "import sys; print('%d.%d' % sys.version_info[:2])")
if ([version]$pyVersion -lt [version]"3.12") { throw "Python 3.12+ required, found $pyVersion" }

if (-not (Test-Path .venv)) {
    Write-Host "Creating virtual environment .venv ..."
    python -m venv .venv
}
Write-Host "Installing dependencies ..."
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.\.venv\Scripts\python.exe -m pip install --quiet -r requirements-dev.txt

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from .env.example (local values only, git-ignored)."
}
Write-Host "`nSetup complete. Next:  docker compose up -d --build"
