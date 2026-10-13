<#
Run the saved KQL files in kql/ against the project's Log Analytics workspace.

Usage (repo root, after `az login`):
  powershell -ExecutionPolicy Bypass -File scripts\run_kql.ps1                          # all files
  powershell -ExecutionPolicy Bypass -File scripts\run_kql.ps1 -Name 21_5xx_by_code     # one file
  powershell -ExecutionPolicy Bypass -File scripts\run_kql.ps1 -Lookback 24h            # override window

Notes: needs the CLI extension `log-analytics` (az extension add --name log-analytics).
Each file's `let lookback = ...;` line is replaced when -Lookback is given. Comment lines are dropped
and the query is joined into one line, because Windows PowerShell 5 cannot pass multi-line
arguments to az reliably. KQL strings in these files use single quotes for the same reason.
#>
param(
    [string]$Name = "",
    [string]$Lookback = "",
    [string]$ResourceGroup = "rg-sredemo-app",
    [string]$Workspace = "log-sredemo"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$wsId = az monitor log-analytics workspace show -g $ResourceGroup -n $Workspace --query customerId -o tsv
if (-not $wsId) { throw "Workspace $Workspace not found in $ResourceGroup (are you logged in?)" }

$files = Get-ChildItem kql\*.kql | Sort-Object Name
if ($Name) { $files = $files | Where-Object { $_.BaseName -eq $Name } }
if (-not $files) { throw "No KQL file matched '$Name'" }

$failures = 0
foreach ($f in $files) {
    $lines = [IO.File]::ReadAllLines($f.FullName) | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith("//") }
    $query = ($lines -join " ")
    if ($Lookback) { $query = $query -replace "let lookback = [^;]+;", "let lookback = $Lookback;" }
    Write-Host "`n=== $($f.BaseName)" -ForegroundColor Cyan
    $out = az monitor log-analytics query -w $wsId --analytics-query $query -o table --only-show-errors 2>&1
    if ($LASTEXITCODE -ne 0) { $failures++; Write-Host "FAILED" -ForegroundColor Red; $out | Select-Object -First 15 }
    elseif (-not $out) { Write-Host "(no rows in this time window)" }
    else { $out }
}
Write-Host ""
if ($failures) { Write-Host "$failures query file(s) FAILED" -ForegroundColor Red; exit 1 }
Write-Host "All $(@($files).Count) query file(s) ran successfully" -ForegroundColor Green
