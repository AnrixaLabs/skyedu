#requires -Version 5.1
<#
Read-only production snapshot -> full-byte-preserving local staging preview.
NO remote uploads, SSH writes, database changes, Nginx changes, or publication.
The password is prompted by OpenSSH interactively and never handled by this script.
#>
[CmdletBinding()]
param(
    [ValidateSet('CaptureAndStage','StageLocal','Verify')]
    [string]$Mode = 'CaptureAndStage',
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$ServerIP = '8.210.9.172',
    [string]$CaptureDir = '',
    [string]$SourceRoot = '',
    [string]$StageDir = '',
    [string]$ReportDir = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$py = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$engine = Join-Path $ProjectRoot 'scripts\course_hub_integration.py'
$lobby = Join-Path $ProjectRoot 'skyed_lobby\site'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { throw 'SKYED_PYTHON_MISSING' }
if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) { throw 'SKYED_INTEGRATION_ENGINE_MISSING' }
if (-not (Test-Path -LiteralPath $lobby -PathType Container)) { throw 'SKYED_LOBBY_MISSING' }

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$workspace = Join-Path $env:USERPROFILE 'Documents\SkyED-CourseHub-Integration'
New-Item -ItemType Directory -Path $workspace -Force | Out-Null
if (-not $StageDir) { $StageDir = Join-Path $workspace ('staged-' + $timestamp) }
if (-not $ReportDir) { $ReportDir = Join-Path $workspace ('report-' + $timestamp) }
if (-not $CaptureDir) { $CaptureDir = Join-Path $workspace ('snapshot-' + $timestamp) }

if ($Mode -eq 'CaptureAndStage') {
    $ipObj = $null
    if (-not [Net.IPAddress]::TryParse($ServerIP, [ref]$ipObj) -or $ipObj.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
        throw 'SKYED_INVALID_REMOTE_SERVER_IP'
    }
    # Actual host ownership must have been independently verified.
    # No automatic acceptance of new SSH host keys.
    foreach ($command in @('ssh.exe','scp.exe')) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "OPENSSH_CLIENT_REQUIRED: $command" }
    }
    if (Test-Path -LiteralPath $CaptureDir) { throw 'SKYED_CAPTURE_DIRECTORY_ALREADY_EXISTS' }
    New-Item -ItemType Directory -Path $CaptureDir | Out-Null
    $remote = 'root@' + $ServerIP
    $root = '/var/www/course.skyed.org/current'
    Write-Host 'SKYED_REMOTE_PREFLIGHT=READ_ONLY'
    Write-Host "REMOTE=$remote PATH=$root"
    $command = "set -eu; test -d '$root'; test -r '$root/index.html'; cd '$root'; printf 'SKYED_REMOTE_SITE_ROOT_READABLE=PASS\n';"
    & ssh.exe '-o' 'StrictHostKeyChecking=yes' '-o' 'ConnectTimeout=15' $remote $command
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_REMOTE_PREFLIGHT_FAILED_NO_SITE_WRITE' }
    Write-Host 'SKYED_REMOTE_CAPTURE=BEGIN_READ_ONLY_SFTP'
    & scp.exe '-o' 'StrictHostKeyChecking=yes' '-o' 'ConnectTimeout=15' '-r' ($remote + ':' + $root + '/.') $CaptureDir
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_REMOTE_CAPTURE_FAILED_NO_SITE_WRITE' }
    $SourceRoot = $CaptureDir
}
elseif ($Mode -eq 'StageLocal' -and (-not $SourceRoot)) { throw 'SKYED_SOURCE_ROOT_REQUIRED_FOR_STAGE_LOCAL' }
elseif ($Mode -eq 'Verify' -and (-not $SourceRoot -or -not $StageDir -or -not $ReportDir)) { throw 'SKYED_VERIFY_REQUIRES_ALL_THREE_PATHS' }

$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
if ($Mode -eq 'Verify') {
    & $py $engine 'verify' '--source' $SourceRoot '--stage' $StageDir '--report' $ReportDir
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_STAGE_VERIFICATION_FAILED' }
    exit 0
}

& $py $engine 'stage' '--source' $SourceRoot '--lobby' $lobby '--output' $StageDir '--report' $ReportDir
if ($LASTEXITCODE -ne 0) { throw 'SKYED_STAGE_BUILD_BLOCKED_NO_SITE_WRITE' }
& $py $engine 'verify' '--source' $SourceRoot '--stage' $StageDir '--report' $ReportDir
if ($LASTEXITCODE -ne 0) { throw 'SKYED_STAGE_VERIFICATION_FAILED' }

Write-Host 'SKYED_COURSE_HUB_INTEGRATION=STAGED_LOCAL_ONLY'
Write-Host "SOURCE_SNAPSHOT=$SourceRoot"
Write-Host "STAGED_SITE=$StageDir"
Write-Host "REVIEW_REPORT=$ReportDir"
Write-Host 'PRODUCTION_DEPLOYMENT=false'
Write-Host 'To preview, run the Python stage server, then open its displayed localhost URL.'
