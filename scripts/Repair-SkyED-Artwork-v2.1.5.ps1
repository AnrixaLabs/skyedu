<#
.SYNOPSIS
  Inspect existing Stage C QA artwork and optionally rebuild only cards.
.DESCRIPTION
  Default PREVIEW is read-only and requires no package installs or media generation.
  -Apply requires reviewed illustration files. Reuses already verified EN/ZH MP3
  bytes without regeneration. Never writes to the original PyCharm source,
  the prior media evidence, WordPress, or GitHub.
.EXAMPLE
  .\Repair-SkyED-Artwork-v2.1.5.ps1
.EXAMPLE
  .\Repair-SkyED-Artwork-v2.1.5.ps1 -ArtworkRoot "$env:USERPROFILE\Downloads\SkyED-Approved-Artwork" -Apply
#>
[CmdletBinding()]
param(
  [string]$EvidenceZip = 'C:\Users\user\Downloads\SkyED-Media-QA-Launch-20261020-125441763\SkyED-Real-Media-QA-Evidence.zip',
  [string]$ExpectedSha256 = '99B90C6BF6723F1F48D62A4C4ED96454D79B08CF7032591CAA87A008852E4219',
  [string]$ArtworkRoot = 'C:\Users\user\PycharmProjects\skyed_automation\asset_library',
  [string]$ExistingQARoot = 'C:\Users\user\Downloads\SkyED-Media-QA-Launch-20261020-125441763',
  [switch]$Apply,
  [string]$OutputRoot = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PyScript = Join-Path $PSScriptRoot 'scripts\qa_reuse_audio_artwork.py'
if (-not (Test-Path -LiteralPath $EvidenceZip -PathType Leaf)) { throw "Evidence ZIP not found: $EvidenceZip" }
if (-not (Test-Path -LiteralPath $PyScript -PathType Leaf)) { throw "Artwork repair script missing: $PyScript" }
$ActualHash = (Get-FileHash -LiteralPath $EvidenceZip -Algorithm SHA256).Hash
if ($ActualHash -ine $ExpectedSha256) { throw "Evidence checksum mismatch. Expected=$ExpectedSha256 Actual=$ActualHash" }
if ($Apply) {
  $Python = Join-Path $ExistingQARoot 'venv\Scripts\python.exe'
  $Repository = Join-Path $ExistingQARoot 'skyedu'
  if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "QA venv Python missing: $Python" }
  if (-not (Test-Path -LiteralPath (Join-Path $Repository 'skyed\cards.py') -PathType Leaf)) {
    throw "QA source checkout missing: $Repository"
  }
} else {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = 'py'
    $Prefix = @('-3')
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Python = 'python'
    $Prefix = @()
  } else { throw 'Python 3 is required' }
}
Write-Host '============================================================'
Write-Host ' SKYED ARTWORK QUALITY REPAIR v2.1.5'
Write-Host '============================================================'
Write-Host 'NO_AUDIO_REGENERATION=true NO_WORDPRESS_WRITE=true NO_ORIGINAL_SOURCE_CHANGE=true'
Write-Host "MODE=$(if($Apply){'REBUILD_NEW_QA_COPY'}else{'READ_ONLY_PREVIEW'})"
Write-Host "ORIGINAL_MEDIA_EVIDENCE=$EvidenceZip"
Write-Host "EVIDENCE_SHA256=$ActualHash"
$ArgsList = @($PyScript, '--evidence', $EvidenceZip, '--expected-sha256', $ExpectedSha256,
              '--artwork', $ArtworkRoot)
if ($Apply) {
  if (-not $OutputRoot) {
    $OutputRoot = Join-Path (Join-Path $env:USERPROFILE 'Downloads') ('SkyED-Artwork-Review-' + (Get-Date -Format 'yyyyMMdd-HHmmssfff'))
  }
  if (Test-Path -LiteralPath $OutputRoot) { throw "Refusing to overwrite output: $OutputRoot" }
  $ArgsList += @('--repo', $Repository, '--output', $OutputRoot, '--apply')
  & $Python @ArgsList
} else {
  & $Python @Prefix @ArgsList
}
$Result = $LASTEXITCODE
Write-Host "ARTWORK_QA_EXIT_CODE=$Result"
if ($Result -ne 0) { Write-Host 'ARTWORK_QA_BLOCKED=Review the JSON error above; no WordPress or TTS writes were attempted.' }
if ($Apply -and $Result -eq 0) {
  Write-Host "ARTWORK_REVIEW_FOLDER=$OutputRoot"
  Write-Host "ARTWORK_REVIEW_HTML=$(Join-Path $OutputRoot 'lesson\review.html')"
  Write-Host "ARTWORK_REVIEW_EVIDENCE=$(Join-Path $OutputRoot 'SkyED-Artwork-Reused-Audio-REVIEW.zip')"
  Write-Host 'IMPORTANT=Technical image checks do not approve image meaning, pronunciation or final WordPress design.'
} elseif (-not $Apply) {
  Write-Host 'NEXT=If status is READY, review image meaning and rights, then rerun THIS script with -Apply. If images are missing or invalid, correct those specific files first.'
  Write-Host 'NO_AUDIO_REGENERATION=true'
}
exit $Result
