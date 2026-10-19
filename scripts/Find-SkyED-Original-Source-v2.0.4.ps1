<#
.SYNOPSIS
  Discover original SkyED Python modules read-only; export after source review.
.EXAMPLE
  .\Find-SkyED-Original-Source-v2.0.4.ps1
.EXAMPLE
  .\Find-SkyED-Original-Source-v2.0.4.ps1 -SourceRoot 'D:\SkyED' -IncludeSource
#>
[CmdletBinding()]
param(
    [string]$SourceRoot = '',
    [string[]]$SearchRoots = @(),
    [switch]$IncludeSource,
    [int]$MaxDepth = 6,
    [int]$MaxDirectories = 50000,
    [string]$OutputDirectory = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Tool = Join-Path $PSScriptRoot 'discover_original_skyed.py'
if (-not (Test-Path -LiteralPath $Tool -PathType Leaf)) {
    throw "The recovery Python tool is missing: $Tool"
}
if ($IncludeSource -and [string]::IsNullOrWhiteSpace($SourceRoot)) {
    throw 'For safety, -IncludeSource REQUIRES -SourceRoot pointing to the exact original project.'
}
if ($MaxDepth -lt 0 -or $MaxDirectories -lt 1) {
    throw 'Invalid scanning bounds.'
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $Downloads = Join-Path $env:USERPROFILE 'Downloads'
    $OutputDirectory = Join-Path $Downloads ('SkyED-Source-Recovery-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
if (-not (Test-Path -LiteralPath $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}
$Report = Join-Path $OutputDirectory 'skyed-original-source-inventory.json'
if (Test-Path -LiteralPath $Report) {
    throw "Refusing to replace earlier evidence: $Report"
}
$PythonCommand = ''
$Prefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = 'py'
    $Prefix = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = 'python'
} else {
    throw 'Python 3.11+ is required; no files modified.'
}
$Arguments = @($Tool, '--report', $Report, '--max-depth', [string]$MaxDepth, '--max-directories', [string]$MaxDirectories)
if (-not [string]::IsNullOrWhiteSpace($SourceRoot)) {
    if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
        throw "Cannot find original project folder: $SourceRoot"
    }
    $Arguments += @('--source-root', $SourceRoot)
} elseif ($SearchRoots.Count -gt 0) {
    foreach ($Root in $SearchRoots) { $Arguments += @('--scan-root', $Root) }
}
if ($IncludeSource) {
    $ZipPath = Join-Path $OutputDirectory 'SkyED-Original-Modules-REVIEW.zip'
    $Arguments += @('--export-zip', $ZipPath)
}
Write-Host '============================================================'
Write-Host ' SKYED ORIGINAL SOURCE RECOVERY 2.0.4'
Write-Host '============================================================'
Write-Host 'NO_GITHUB_WRITE=true NO_WORDPRESS_WRITE=true NO_SOURCE_OVERWRITE=true'
Write-Host "REPORT_PATH=$Report"
& $PythonCommand @Prefix @Arguments
$Exit = $LASTEXITCODE
Write-Host "RECOVERY_EXIT_CODE=$Exit"
if ($Exit -eq 0) {
    Write-Host "INVENTORY_FILE=$Report"
    if ($IncludeSource) {
        Write-Host "SOURCE_REVIEW_ARCHIVE=$ZipPath"
        Write-Warning 'Inspect original Python modules for embedded credentials/private data before sharing.'
    } else {
        Write-Host 'NEXT=Read source_root from inventory; rerun with -SourceRoot and -IncludeSource.'
    }
} elseif ($Exit -eq 2) {
    Write-Warning 'No original candidates found; retry with -SearchRoots.'
} else {
    Write-Warning 'Recovery blocked; review error.'
}
exit $Exit
