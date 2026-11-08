#requires -Version 5.1
<#[SkyED] Local production-root candidate, no SSH or production write.#>
[CmdletBinding()]
param(
    [ValidateSet('BuildBrightRoot','VerifyBrightRoot','PreviewBrightRoot','LegacyStage')]
    [string]$Mode = 'BuildBrightRoot',
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$SourceRoot = '',
    [string]$CandidateDir = '',
    [string]$ReportDir = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$py = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$release = Join-Path $ProjectRoot 'scripts\course_hub_release.py'
$legacy = Join-Path $ProjectRoot 'scripts\course_hub_integration.py'
$lobby = Join-Path $ProjectRoot 'skyed_lobby\site'
foreach ($required in @($py, $release, $legacy, (Join-Path $lobby 'index.html'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "SKYED_V250_REQUIRED_FILE_MISSING: $required" }
}
$base = Join-Path $HOME 'Documents\SkyED-CourseHub-Integration'
if (-not $SourceRoot) {
    $found = @(Get-ChildItem -LiteralPath $base -Directory -Filter 'snapshot-*' -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'index.html') -PathType Leaf } |
        Sort-Object LastWriteTime -Descending)
    if ($found.Count -lt 1) { throw 'SKYED_V250_AUTHORITATIVE_SOURCE_CAPTURE_NOT_FOUND' }
    $SourceRoot = $found[0].FullName
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
if (-not $CandidateDir -and $Mode -eq 'BuildBrightRoot') {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $CandidateDir = Join-Path $base ("bright-candidate-$stamp")
    $ReportDir = Join-Path $base ("bright-report-$stamp")
}
if (-not $CandidateDir -and $Mode -ne 'BuildBrightRoot') {
    $items = @(Get-ChildItem -LiteralPath $base -Directory -Filter 'bright-candidate-*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($items.Count -eq 0) { throw 'SKYED_V250_CANDIDATE_NOT_FOUND' }
    $CandidateDir = $items[0].FullName
}
if (-not $ReportDir) {
    $suffix = [IO.Path]::GetFileName($CandidateDir).Replace('bright-candidate-','')
    $ReportDir = Join-Path $base ("bright-report-$suffix")
}
switch ($Mode) {
    BuildBrightRoot {
        & $py $release build --source $SourceRoot --lobby $lobby --output $CandidateDir --report $ReportDir
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_CANDIDATE_BUILD_FAILED' }
        & $py $release verify --source $SourceRoot --candidate $CandidateDir --report $ReportDir
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_CANDIDATE_VERIFY_FAILED' }
        Write-Host "BRIGHT_ROOT_CANDIDATE=$CandidateDir"
        Write-Host "RELEASE_REPORT=$ReportDir"
    }
    VerifyBrightRoot {
        & $py $release verify --source $SourceRoot --candidate $CandidateDir --report $ReportDir
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_CANDIDATE_VERIFY_FAILED' }
    }
    PreviewBrightRoot {
        & $py $release preview --candidate $CandidateDir
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_ROOT_PREVIEW_FAILED' }
    }
    LegacyStage {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $target = Join-Path $base "staged-$stamp"
        $receipt = Join-Path $base "report-$stamp"
        & $py $legacy stage --source $SourceRoot --lobby $lobby --output $target --report $receipt
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_LEGACY_STAGE_FAILED' }
    }
}
