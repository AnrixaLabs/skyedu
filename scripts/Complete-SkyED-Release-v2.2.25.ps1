# SkyED renderer v2.2.26 — minimal Windows PowerShell 5.1 launcher.
# Requires the existing Stage G browser virtual environment (Playwright + Edge).
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$CandidateZip
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Engine = Join-Path $env:USERPROFILE 'Downloads\SkyED-StageG-Isolated-BrowserTools-v2.2.1\venv\Scripts\python.exe'
$Runner = Join-Path $Here 'finish_skyed_renderer_v225.py'
$Remote = Join-Path $Here 'skyed_renderer_remote_v225.sh'
if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) {
    throw "Missing final release controller: $Runner"
}
if (-not (Test-Path -LiteralPath $Remote -PathType Leaf)) {
    throw "Missing remote transaction controller: $Remote"
}
if (-not (Test-Path -LiteralPath $Engine -PathType Leaf)) {
    throw "Stage G browser Python is not available: $Engine"
}
$Arguments = @($Runner)
if ($Apply) { $Arguments += '--apply' }
if (-not [string]::IsNullOrWhiteSpace($CandidateZip)) {
    if (-not (Test-Path -LiteralPath $CandidateZip -PathType Leaf)) {
        throw "Candidate ZIP not found: $CandidateZip"
    }
    $Arguments += @('--candidate', (Resolve-Path -LiteralPath $CandidateZip).Path)
}
& $Engine @Arguments
$Result = $LASTEXITCODE
if ($Result -ne 0) {
    throw "SkyED final controller exited with code $Result; inspect SkyED-Final-Release-v2.2.26-*.json in Downloads."
}
