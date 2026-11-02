#requires -Version 5.1
<#
SkyED Control Panel v2.3.0 + integrated Course Hub Lobby Designer.
Additive, reversible install. Original pyside_gui.py, run_pipeline.py,
assets, secrets and production sites remain untouched.

PowerShell:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\SkyED-ControlPanel-Lobby-v2.3.0\scripts\Install-SkyED-ControlPanel-v2.3.0.ps1" -ProjectRoot "C:\Users\user\PycharmProjects\skyed_automation"
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$SourceRoot = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $SourceRoot) { $SourceRoot = Split-Path -Parent $PSScriptRoot }
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$manifestPath = Join-Path $SourceRoot 'member-sha256.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'SKYED_V230_MEMBER_MANIFEST_MISSING' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.version -ne '2.3.0' -or $manifest.kind -ne 'additive-control-panel-and-private-lobby') {
    throw 'SKYED_V230_MANIFEST_VERSION_MISMATCH'
}
foreach ($path in @('pyside_gui.py','run_pipeline.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $path) -PathType Leaf)) {
        throw "SKYED_REQUIRED_LEGACY_SOURCE_MISSING: $path"
    }
}
$py = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$pyw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { throw 'SKYED_PYTHON_VENV_MISSING' }
if (-not (Test-Path -LiteralPath $pyw -PathType Leaf)) { throw 'SKYED_PYTHONW_VENV_MISSING' }

$properties = @($manifest.files.PSObject.Properties)
if ($properties.Count -lt 15 -or $properties.Count -gt 50) { throw 'SKYED_V230_MANIFEST_MEMBER_COUNT_INVALID' }
$allowed = '^(skyed_control_panel\.py|skyed_control/(?:__init__|registry|lobby_workspace)\.py|skyed_lobby/(?:site|tools|scripts|tests)/[a-zA-Z0-9_./-]+|scripts/Install-SkyED-ControlPanel-v2\.3\.0\.ps1|docs/CONTROL-PANEL-v2\.3\.0\.md)$'
foreach ($property in $properties) {
    $relative = [string]$property.Name
    if ($relative -notmatch $allowed -or $relative.Contains('..') -or $relative.Contains('\\')) {
        throw "SKYED_V230_UNEXPECTED_MEMBER: $relative"
    }
    $source = Join-Path $SourceRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "SKYED_V230_MEMBER_MISSING: $relative" }
    $actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = [string]$property.Value
    if ($actual -ne $expected.ToLowerInvariant()) { throw "SKYED_V230_HASH_MISMATCH: $relative" }
}
Write-Host "SKYED_V230_MANIFEST=PASS members=$($properties.Count)"

# Preserve existing user-edited lobby.json: source updates must not reset drafts.
$contentPath = 'skyed_lobby/site/content/lobby.json'
$existingContent = Join-Path $ProjectRoot ($contentPath.Replace('/', '\'))
$hasContent = Test-Path -LiteralPath $existingContent -PathType Leaf
if ($hasContent) {
    & $py -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8-sig")); assert d.get("schemaVersion")==1; print("SKYED_PREVIOUS_LOBBY_CONTENT=PRESERVED")' $existingContent
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_EXISTING_LOBBY_CONTENT_INVALID_NO_OVERWRITE' }
}

$backup = Join-Path $ProjectRoot ('backups\control-panel-v2.3.0-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$previous = @{}
$success = $false
$desktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SkyED Control Panel.lnk'
$menuFolder = Join-Path ([Environment]::GetFolderPath('Programs')) 'Sky Education'
$menuLink = Join-Path $menuFolder 'SkyED Control Panel.lnk'
$links = @($desktopLink,$menuLink)
$oldLink = @{}

try {
    foreach ($property in $properties) {
        $relative = [string]$property.Name
        if ($relative -eq $contentPath -and $hasContent) { continue }
        if ($relative -match '^(scripts/|docs/)') { continue }  # Installer/docs stay in release archive.
        $src = Join-Path $SourceRoot ($relative.Replace('/', '\'))
        $dst = Join-Path $ProjectRoot ($relative.Replace('/', '\'))
        $wasPresent = Test-Path -LiteralPath $dst -PathType Leaf
        $previous[$relative] = $wasPresent
        if ($wasPresent) {
            $copy = Join-Path $backup ($relative.Replace('/', '\'))
            New-Item -ItemType Directory -Path (Split-Path -Parent $copy) -Force | Out-Null
            Copy-Item -LiteralPath $dst -Destination $copy -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }

    # Compile all code and execute a real Qt GUI smoke test + local server tests.
    $winDir = [Environment]::GetEnvironmentVariable('WINDIR', 'Process')
    if ([string]::IsNullOrWhiteSpace($winDir)) { $winDir = [Environment]::GetEnvironmentVariable('SystemRoot', 'Process') }
    if ([string]::IsNullOrWhiteSpace($winDir)) { throw 'SKYED_WINDOWS_DIRECTORY_NOT_FOUND' }
    $fonts = Join-Path $winDir 'Fonts'
    if (-not (Test-Path -LiteralPath $fonts -PathType Container)) { throw 'SKYED_WINDOWS_FONTS_NOT_FOUND' }
    $oldPlatform = [Environment]::GetEnvironmentVariable('QT_QPA_PLATFORM', 'Process')
    $oldFonts = [Environment]::GetEnvironmentVariable('QT_QPA_FONTDIR', 'Process')
    $oldQtEngine = [Environment]::GetEnvironmentVariable('QTWEBENGINE_DISABLE_SANDBOX', 'Process')
    Push-Location $ProjectRoot
    try {
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', 'offscreen', 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $fonts, 'Process')
        & $py -m py_compile 'skyed_control_panel.py' 'skyed_control\registry.py' 'skyed_control\lobby_workspace.py' 'skyed_lobby\scripts\control_server.py'
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V230_PYTHON_COMPILE_FAILED' }
        & $py 'skyed_control_panel.py' --smoke-test
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V230_QT_STARTUP_FAILED' }
        & $py -m unittest discover -s skyed_lobby\tests -p 'test_control_lobby.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V230_LOCAL_SERVER_TESTS_FAILED' }
    } finally {
        Pop-Location
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', $oldPlatform, 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $oldFonts, 'Process')
    }
    Write-Host 'SKYED_V230_LOCAL_QA=PASS'

    # Shortcut mutation comes last. Back up previous shortcut files first.
    foreach ($linkPath in $links) {
        $oldLink[$linkPath] = Test-Path -LiteralPath $linkPath -PathType Leaf
        if ($oldLink[$linkPath]) {
            $copy = Join-Path $backup ('shortcuts\' + [IO.Path]::GetFileName((Split-Path -Parent $linkPath)) + '\SkyED Control Panel.lnk')
            New-Item -ItemType Directory -Path (Split-Path -Parent $copy) -Force | Out-Null
            Copy-Item -LiteralPath $linkPath -Destination $copy -Force
            $oldLink[$linkPath + ':backup'] = $copy
        }
    }
    $icon = Join-Path $ProjectRoot 'assets\branding\sky_logo.ico'
    if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) { $icon = $pyw }
    $shell = New-Object -ComObject WScript.Shell
    New-Item -ItemType Directory -Path $menuFolder -Force | Out-Null
    foreach ($linkPath in $links) {
        $shortcut = $shell.CreateShortcut($linkPath)
        $shortcut.TargetPath = $pyw
        $shortcut.Arguments = '"' + (Join-Path $ProjectRoot 'skyed_control_panel.py') + '"'
        $shortcut.WorkingDirectory = $ProjectRoot
        $shortcut.IconLocation = $icon
        $shortcut.Description = 'SkyED Control Panel 2.3.0 - Lobby Designer'
        $shortcut.Save()
        Write-Host "SKYED_V230_SHORTCUT=$linkPath"
    }
    $success = $true
} finally {
    if (-not $success) {
        foreach ($relative in @($previous.Keys)) {
            $dst = Join-Path $ProjectRoot ($relative.Replace('/', '\'))
            if ($previous[$relative]) {
                $src = Join-Path $backup ($relative.Replace('/', '\'))
                if (Test-Path -LiteralPath $src -PathType Leaf) { Copy-Item -LiteralPath $src -Destination $dst -Force }
            } elseif (Test-Path -LiteralPath $dst -PathType Leaf) {
                Remove-Item -LiteralPath $dst -Force
            }
        }
        foreach ($linkPath in $links) {
            if (-not $oldLink.ContainsKey($linkPath)) { continue }
            if ($oldLink[$linkPath]) {
                $copy = [string]$oldLink[$linkPath + ':backup']
                if (Test-Path -LiteralPath $copy -PathType Leaf) { Copy-Item -LiteralPath $copy -Destination $linkPath -Force }
            } elseif (Test-Path -LiteralPath $linkPath -PathType Leaf) {
                Remove-Item -LiteralPath $linkPath -Force
            }
        }
        Write-Warning "SKYED_V230_INSTALL=ROLLED_BACK backups=$backup"
    }
}
Write-Host "SKYED_V230_INSTALL=PASS root=$ProjectRoot"
Write-Host 'LOBBY_DESIGNER=INTEGRATED_WIRED_TO_PRIVATE_LOCAL_PREVIEW'
Write-Host 'Existing user lobby.json preserved if present. Production website remains unchanged.'
