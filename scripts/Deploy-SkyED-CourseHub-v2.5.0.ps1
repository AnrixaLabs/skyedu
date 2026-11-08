#requires -Version 5.1
<# Strict-host-key, review-gated publication wrapper. Default is READ ONLY. #>
[CmdletBinding()]
param(
    [ValidateSet('Preflight','Publish','Rollback')][string]$Mode = 'Preflight',
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$ServerIP = '8.210.9.172',
    [string]$SourceRoot = '',
    [string]$CandidateDir = '',
    [string]$ReportDir = '',
    [string]$ApprovalFile = '',
    [string]$ReceiptFile = '',
    [string]$Confirm = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$py = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$script = Join-Path $ProjectRoot 'scripts\course_hub_deploy.py'
foreach ($file in @($py,$script)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "SKYED_V250_DEPLOY_TOOL_MISSING: $file" } }
if ($Mode -eq 'Rollback') {
    if (-not $ReceiptFile -or $Confirm -cne 'ROLLBACK SKYED COURSE HUB') { throw 'SKYED_ROLLBACK_NEEDS_EXACT_RECEIPT_AND_CONFIRMATION' }
    & $py $script --mode rollback --server-ip $ServerIP --receipt $ReceiptFile --confirm $Confirm
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_ROLLBACK_FAILED' }
    exit 0
}
if (-not $CandidateDir -or -not $ReportDir -or -not $SourceRoot) {
    throw 'SKYED_V250_PRECISE_SOURCE_CANDIDATE_REPORT_REQUIRED'
}
if ($Mode -eq 'Preflight') {
    & $py $script --mode preflight --server-ip $ServerIP --source $SourceRoot --candidate $CandidateDir --report $ReportDir
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_READONLY_PREFLIGHT_FAILED' }
    exit 0
}
if ($Confirm -cne 'PUBLISH SKYED BRIGHT 2.5.0') { throw 'SKYED_V250_EXPLICIT_CONFIRMATION_REQUIRED' }
if (-not $ApprovalFile -or -not $ReceiptFile) { throw 'SKYED_V250_TEACHER_REVIEW_AND_RECEIPT_REQUIRED' }
& $py $script --mode deploy --server-ip $ServerIP --source $SourceRoot --candidate $CandidateDir --report $ReportDir --approval $ApprovalFile --receipt $ReceiptFile --confirm $Confirm
if ($LASTEXITCODE -ne 0) { throw 'SKYED_V250_PRODUCTION_DEPLOY_FAILED' }
