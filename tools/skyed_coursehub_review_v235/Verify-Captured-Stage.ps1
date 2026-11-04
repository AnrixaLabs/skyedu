#requires -Version 5.1
<#
.SYNOPSIS
Offline qualification for a previously staged SkyED Course Hub.
.DESCRIPTION
By default, discovers the latest matching report-*/staged-* directories under
Documents\SkyED-CourseHub-Integration. Also accepts a combined ZIP, or an
explicit matched directory pair. Read-only for the capture and staged website;
only a separate review receipt is written. No network or production actions.
#>
[CmdletBinding()]
param(
    [string]$Archive = '',
    [string]$ReportDir = '',
    [string]$StageDir = '',
    [string]$Workspace = (Join-Path $HOME 'Documents\SkyED-CourseHub-Integration'),
    [string]$Output = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$verifier = Join-Path $PSScriptRoot 'scripts\verify_stage_report.py'
if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
    throw 'SKYED_REVIEW_VERIFIER_NOT_FOUND'
}

# Keep all receipts separate from the original data and previous gate receipts.
if ([string]::IsNullOrWhiteSpace($Output)) {
    $reviewDir = Join-Path $Workspace 'review-receipts'
    $name = 'review-gate-v2.3.5-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.json'
    $Output = Join-Path $reviewDir $name
}

if (([bool]$ReportDir) -xor ([bool]$StageDir)) {
    throw 'SKYED_REPORT_AND_STAGE_DIRS_MUST_BOTH_BE_SET'
}
if ($ReportDir -and $Archive) {
    throw 'SKYED_REVIEW_SOURCE_AMBIGUOUS'
}

$pythonArgs = @($verifier)
if ($ReportDir -and $StageDir) {
    if (-not (Test-Path -LiteralPath $ReportDir -PathType Container)) {
        throw "SKYED_REPORT_DIRECTORY_NOT_FOUND: $ReportDir"
    }
    if (-not (Test-Path -LiteralPath $StageDir -PathType Container)) {
        throw "SKYED_STAGE_DIRECTORY_NOT_FOUND: $StageDir"
    }
    Write-Host 'SKYED_REVIEW_SOURCE=EXPLICIT_LOCAL_DIRECTORIES'
    $pythonArgs += @('--report-dir', $ReportDir, '--stage-dir', $StageDir)
}
elseif ($Archive -and (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    Write-Host 'SKYED_REVIEW_SOURCE=COMBINED_ZIP'
    $pythonArgs += @($Archive)
}
else {
    # The earlier v2.3.4 command wrongly assumed that an archive uploaded to
    # ChatGPT also existed in Windows Downloads. It need not exist there.
    # Recover the equivalent paired local report/stage only when the timestamps
    # match. Never silently select an unrelated capture.
    if (-not (Test-Path -LiteralPath $Workspace -PathType Container)) {
        throw "SKYED_WORKSPACE_NOT_FOUND: $Workspace"
    }
    $pythonArgs += @('--workspace', $Workspace)
    if ($Archive) {
        $basename = [System.IO.Path]::GetFileNameWithoutExtension($Archive)
        if ($basename -notmatch '^report-([0-9]{8}-[0-9]{6})$') {
            throw "SKYED_ARCHIVE_NOT_FOUND_AND_NAME_INVALID: $Archive"
        }
        $stamp = $Matches[1]
        Write-Host "SKYED_ARCHIVE_NOT_LOCAL=USING_MATCHED_STAGE_DIRECTORIES stamp=$stamp"
        $pythonArgs += @('--stamp', $stamp)
    }
    Write-Host "SKYED_REVIEW_SOURCE=DISCOVERED_LOCAL_STAGE workspace=$Workspace"
}
$pythonArgs += @('--output', $Output)

$py = Get-Command 'py.exe' -ErrorAction SilentlyContinue
if ($null -ne $py) {
    & $py.Source '-3' @pythonArgs
}
else {
    $py = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($null -eq $py) { throw 'SKYED_PYTHON3_REQUIRED' }
    & $py.Source @pythonArgs
}
if ($LASTEXITCODE -ne 0) {
    throw "SKYED_V235_STAGE_REVIEW_GATE_BLOCKED; audit_receipt=$Output"
}
Write-Host 'SKYED_V235_TECHNICAL_STAGE=PASS'
Write-Host 'SKYED_V235_TEACHER_REVIEW=PENDING'
Write-Host 'SKYED_V235_PRODUCTION_APPROVAL=false'
Write-Host "AUDIT_RECEIPT=$Output"
