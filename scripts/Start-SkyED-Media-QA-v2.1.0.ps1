<#
.SYNOPSIS
  SkyED Phase C: real local EN/ZH audio and image media QA, never WordPress.

.DESCRIPTION
  Clones the existing development branch into a fresh Downloads folder.
  Installs isolated QA dependencies including Edge TTS and mutagen.
  Explicitly sends the generic sample text to Edge TTS for audio synthesis.
  Uses local-assets-only image mode, and requires teacher picture review.
  Refuses to overwrite existing QA evidence; never writes to original PyCharm.
#>
[CmdletBinding()]
param([string]$OutputRoot = '')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Branch = 'feature/homework-automation-v2'
$RepositoryUrl = 'https://github.com/AnrixaLabs/skyedu.git'
if (-not $OutputRoot) {
    $Stamp = Get-Date -Format 'yyyyMMdd-HHmmssfff'
    $OutputRoot = Join-Path (Join-Path $env:USERPROFILE 'Downloads') "SkyED-Real-Media-QA-$Stamp"
}
if (Test-Path -LiteralPath $OutputRoot) {
    throw "Refusing to overwrite existing QA workspace: $OutputRoot"
}
New-Item -ItemType Directory -Path $OutputRoot -ErrorAction Stop | Out-Null
$Repo = Join-Path $OutputRoot 'skyedu'
$MediaRun = Join-Path $OutputRoot 'media-run'
$Log = Join-Path $OutputRoot 'dependencies.log'
$ReportFile = Join-Path $OutputRoot 'launcher-report.json'
$Report = [ordered]@{
    schema = 'skyed.media.qa.v2.1.0'
    requested_branch = $Branch
    original_pycharm_source_modified = $false
    wordpress_modified = $false
    published_posts = 0
    teacher_review_required = $true
    started_local = (Get-Date).ToString('o')
    status = 'STARTED'
}
$Exit = 2
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git for Windows is required'
    }
    & git clone --quiet --branch $Branch --single-branch --depth 1 $RepositoryUrl $Repo
    if ($LASTEXITCODE -ne 0) {
        throw "Git clone failed with exit code $LASTEXITCODE"
    }
    $GitSha = @(& git -C $Repo rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $GitSha.Count -ne 1) {
        throw 'Cannot prove development commit'
    }
    $Report.commit = ([string]$GitSha[0]).Trim()
    Write-Host "MEDIA_QA_COMMIT=$($Report.commit)"

    $Venv = Join-Path $OutputRoot 'venv'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $Venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $Venv
    } else {
        throw 'Python 3 required'
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Isolated QA virtualenv creation failed'
    }
    $Python = Join-Path $Venv 'Scripts\python.exe'
    $Capture = Join-Path $Repo 'scripts\qa_capture.py'
    $MediaQA = Join-Path $Repo 'scripts\qa_real_media.py'
    if (-not (Test-Path -LiteralPath $Python) -or
        -not (Test-Path -LiteralPath $Capture) -or
        -not (Test-Path -LiteralPath $MediaQA)) {
        throw 'Missing isolated Python, capture helper, or media QA script'
    }

    $Packages = @(
        'python-dotenv>=1,<2',
        'requests>=2.31,<3',
        'Pillow>=10,<13',
        'numpy>=1.26,<3',
        'edge-tts>=6,<9',
        'mutagen>=1.47,<2'
    )
    & $Python $Capture --log $Log --timeout 1800 -- -m pip install @Packages
    if ($LASTEXITCODE -ne 0) {
        throw "QA dependency installation failed; see $Log"
    }

    Write-Host 'REAL_MEDIA_QA_NETWORK=EDGE_TTS_ONLY'
    Write-Host 'WORDPRESS_PUBLISH=DISABLED'
    & $Python $MediaQA --repo $Repo --output-root $MediaRun --generate --timeout 480
    $Exit = $LASTEXITCODE
    $Report.status = if ($Exit -eq 0) { 'TECHNICAL_MEDIA_PASS' } else { 'BLOCKED' }
}
catch {
    $Report.status = 'BLOCKED'
    $Report.error = $_.Exception.Message
    $Exit = 2
    Write-Warning "Media QA blocked: $($Report.error)"
}
finally {
    $Report.finished_local = (Get-Date).ToString('o')
    $Report | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $ReportFile -Encoding UTF8
    $OriginalZip = Join-Path $MediaRun 'SkyED-Real-Media-QA-Evidence.zip'
    $Deliverable = Join-Path $OutputRoot 'SkyED-Real-Media-QA-Evidence.zip'
    if (Test-Path -LiteralPath $OriginalZip -PathType Leaf) {
        Copy-Item -LiteralPath $OriginalZip -Destination $Deliverable -ErrorAction Stop
    } else {
        $Files = @($ReportFile)
        if (Test-Path -LiteralPath $Log -PathType Leaf) {
            $Files += $Log
        }
        Compress-Archive -LiteralPath $Files -DestinationPath $Deliverable -CompressionLevel Optimal
    }
    $Hash = (Get-FileHash -LiteralPath $Deliverable -Algorithm SHA256).Hash
    Write-Host "MEDIA_QA_STATUS=$($Report.status)"
    Write-Host "MEDIA_QA_EVIDENCE_ZIP=$Deliverable"
    Write-Host "MEDIA_QA_EVIDENCE_SHA256=$Hash"
    Write-Host 'MEDIA_QA_REQUIRES_TEACHER_IMAGE_AUDIO_REVIEW=true'
}
exit $Exit
