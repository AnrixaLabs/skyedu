#requires -Version 5.1
<#
Installs only the additive SkyED Control Panel v2.2.1 files into the user's
existing Windows source tree. Does not touch existing automation, .env,
gui_config.json, WordPress, SSH, Course Hub or any production database.

Usage after extracting the release ZIP:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\Install-SkyED-ControlPanel-v2.2.1.ps1" -ProjectRoot "C:\Users\user\PycharmProjects\skyed_automation"
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$SourceRoot = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $SourceRoot) {
    $SourceRoot = Split-Path -Parent $PSScriptRoot
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$manifestPath = Join-Path $SourceRoot 'member-sha256.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'SKYED_MEMBER_MANIFEST_MISSING' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.version -ne '2.2.1' -or $manifest.kind -ne 'additive-control-panel-overlay') {
    throw 'SKYED_MEMBER_MANIFEST_VERSION_MISMATCH'
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'pyside_gui.py') -PathType Leaf)) {
    throw 'SKYED_LEGACY_GUI_MISSING'
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'run_pipeline.py') -PathType Leaf)) {
    throw 'SKYED_LEGACY_PIPELINE_MISSING'
}
$py = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$pyw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { throw "SKYED_VENV_PYTHON_MISSING: $py" }
if (-not (Test-Path -LiteralPath $pyw -PathType Leaf)) { throw "SKYED_VENV_PYTHONW_MISSING: $pyw" }

$relatives = @(
    'skyed_control_panel.py',
    'skyed_control\__init__.py',
    'skyed_control\registry.py'
)
if (@($manifest.files.PSObject.Properties).Count -ne 5) {
    throw 'SKYED_UNEXPECTED_MEMBER_COUNT'
}
foreach ($relative in @($manifest.files.PSObject.Properties.Name)) {
    if ($relative -notmatch '^(skyed_control_panel\.py|skyed_control/(?:__init__|registry)\.py|scripts/Install-SkyED-ControlPanel-v2\.2\.1\.ps1|docs/CONTROL-PANEL-v2\.2\.1\.md)$') {
        throw "SKYED_UNEXPECTED_MEMBER: $relative"
    }
    $src = Join-Path $SourceRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "SKYED_MEMBER_MISSING: $relative" }
    $actual = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = [string]$manifest.files.PSObject.Properties[$relative].Value
    if ($actual -ne $expected.ToLowerInvariant()) { throw "SKYED_MEMBER_HASH_MISMATCH: $relative" }
}
Write-Host 'SKYED_CONTROL_ARCHIVE_HASHES=PASS'

$backup = Join-Path $ProjectRoot ("backups\control-panel-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$hadPrevious = @{}
$success = $false
try {
    foreach ($relative in $relatives) {
        $dst = Join-Path $ProjectRoot $relative
        $src = Join-Path $SourceRoot $relative
        $old = Test-Path -LiteralPath $dst -PathType Leaf
        $hadPrevious[$relative] = $old
        if ($old) {
            $copy = Join-Path $backup $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $copy) -Force | Out-Null
            Copy-Item -LiteralPath $dst -Destination $copy -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }

    # Qt offscreen's basic font backend does not automatically use Windows fonts.
    # This affects the installation smoke test only; the normal Windows GUI
    # already uses the operating system's font stack. Do not install fonts.
    $winDir = [Environment]::GetEnvironmentVariable('WINDIR', 'Process')
    if ([string]::IsNullOrWhiteSpace($winDir)) {
        $winDir = [Environment]::GetEnvironmentVariable('SystemRoot', 'Process')
    }
    if ([string]::IsNullOrWhiteSpace($winDir)) { throw 'SKYED_WINDOWS_DIRECTORY_NOT_FOUND' }
    $windowsFonts = Join-Path $winDir 'Fonts'
    if (-not (Test-Path -LiteralPath $windowsFonts -PathType Container)) {
        throw 'SKYED_WINDOWS_FONTS_NOT_FOUND'
    }

    # Preserve caller environment exactly, including a pre-existing Qt setup.
    $previousPlatform = [Environment]::GetEnvironmentVariable('QT_QPA_PLATFORM', 'Process')
    $previousFontDir = [Environment]::GetEnvironmentVariable('QT_QPA_FONTDIR', 'Process')
    try {
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', 'offscreen', 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $windowsFonts, 'Process')
        Push-Location $ProjectRoot
        try {
            & $py -m py_compile 'skyed_control_panel.py' 'skyed_control\registry.py' 'skyed_control\__init__.py'
            if ($LASTEXITCODE -ne 0) { throw 'SKYED_CONTROL_COMPILE_FAILED' }
            & $py 'skyed_control_panel.py' --smoke-test
            if ($LASTEXITCODE -ne 0) { throw 'SKYED_CONTROL_QT_SMOKE_FAILED' }
        } finally {
            Pop-Location
        }
    } finally {
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', $previousPlatform, 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $previousFontDir, 'Process')
    }
    Write-Host 'SKYED_CONTROL_QT_SMOKE=PASS'

    $icon = Join-Path $ProjectRoot 'assets\branding\sky_logo.ico'
    if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) { $icon = $pyw }
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Sky Education'
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
    foreach ($linkPath in @(
        (Join-Path $desktop 'SkyED Control Panel.lnk'),
        (Join-Path $startMenu 'SkyED Control Panel.lnk')
    )) {
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = $pyw
        $link.Arguments = '"' + (Join-Path $ProjectRoot 'skyed_control_panel.py') + '"'
        $link.WorkingDirectory = $ProjectRoot
        $link.IconLocation = $icon
        $link.Description = 'SkyED Control Panel 2.2.1'
        $link.Save()
        Write-Host "SKYED_SHORTCUT_CREATED=$linkPath"
    }
    $success = $true
}
finally {
    if (-not $success) {
        foreach ($relative in $relatives) {
            if (-not $hadPrevious.ContainsKey($relative)) { continue }
            $dst = Join-Path $ProjectRoot $relative
            if ($hadPrevious[$relative]) {
                $copy = Join-Path $backup $relative
                if (Test-Path -LiteralPath $copy -PathType Leaf) {
                    Copy-Item -LiteralPath $copy -Destination $dst -Force
                }
            } elseif (Test-Path -LiteralPath $dst -PathType Leaf) {
                Remove-Item -LiteralPath $dst -Force
            }
        }
        Write-Warning 'SKYED_CONTROL_INSTALL=ROLLED_BACK_TO_PRIOR_SOURCE'
    }
}
Write-Host "SKYED_CONTROL_INSTALL=PASS version=2.2.1 root=$ProjectRoot"
Write-Host 'Production sites and existing automation code were not changed.'
