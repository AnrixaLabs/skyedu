#requires -Version 5.1
<#
SkyED Control Panel v2.4.0 — Lobby Designer and safe Course Hub integration.
Additive, reversible install. Original pyside_gui.py, run_pipeline.py,
assets, secrets and production sites remain untouched.

PowerShell:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\SkyED-ControlPanel-Bright-v2.4.0\scripts\Install-SkyED-ControlPanel-v2.4.0.ps1" -ProjectRoot "C:\Users\user\PycharmProjects\skyed_automation"
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\user\PycharmProjects\skyed_automation',
    [string]$SourceRoot = '',
    [switch]$SkipShortcuts  # Intended for disposable Windows CI projects only.
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $SourceRoot) { $SourceRoot = Split-Path -Parent $PSScriptRoot }
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot -ErrorAction Stop).Path
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$manifestPath = Join-Path $SourceRoot 'member-sha256.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'SKYED_V240_MEMBER_MANIFEST_MISSING' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.version -ne '2.4.0' -or $manifest.kind -ne 'additive-control-panel-and-private-lobby-integration') {
    throw 'SKYED_V240_MANIFEST_VERSION_MISMATCH'
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

$expectedMembers = @(
    'docs/CONTROL-PANEL-v2.3.3.md',
    'docs/RELEASE-CHECKPOINT.json',
    'scripts/Install-SkyED-ControlPanel-v2.3.3.ps1',
    'scripts/Start-SkyED-CourseHub-Integration-v2.3.3.ps1',
    'scripts/course_hub_integration.py',
    'scripts/package_control_panel_v233.py',
    'scripts/validate_lobby_content_v233.py',
    'skyed_control/__init__.py',
    'skyed_control/integration_workspace.py',
    'skyed_control/lobby_workspace.py',
    'skyed_control/registry.py',
    'skyed_control_panel.py',
    'skyed_lobby/scripts/control_server.py',
    'skyed_lobby/scripts/preview.py',
    'skyed_lobby/site/assets/app.js',
    'skyed_lobby/site/assets/favicon.svg',
    'skyed_lobby/site/assets/media/README.txt',
    'skyed_lobby/site/assets/styles.css',
    'skyed_lobby/site/content/lobby.json',
    'skyed_lobby/site/index.html',
    'skyed_lobby/tests/test_browser_lobby.py',
    'skyed_lobby/tests/test_control_lobby.py',
    'skyed_lobby/tools/edit-lobby.html',
    'skyed_lobby/tools/editor.css',
    'skyed_lobby/tools/editor.js',
    'tests/test_course_hub_integration.py',
    'tests/test_course_hub_integration_qt.py',
    'tests/test_install_v233.py',
    'tests/test_pilot_route_reconciliation.py',
    'skyed_lobby/site/assets/illustrations/hero-art.webp',
    'skyed_lobby/site/assets/illustrations/program-art.webp',
    'skyed_lobby/site/assets/illustrations/lesson-art.webp',
    'skyed_lobby/site/assets/illustrations/path-1.webp',
    'skyed_lobby/site/assets/illustrations/path-2.webp',
    'skyed_lobby/site/assets/illustrations/path-3.webp',
    'skyed_lobby/site/assets/illustrations/path-4.webp',
    'skyed_lobby/site/assets/illustrations/path-5.webp',
    'skyed_lobby/site/assets/illustrations/topic-01.webp',
    'skyed_lobby/site/assets/illustrations/topic-02.webp',
    'skyed_lobby/site/assets/illustrations/topic-03.webp',
    'skyed_lobby/site/assets/illustrations/topic-04.webp',
    'skyed_lobby/site/assets/illustrations/topic-05.webp',
    'skyed_lobby/site/assets/illustrations/topic-06.webp',
    'skyed_lobby/site/assets/illustrations/topic-07.webp',
    'skyed_lobby/site/assets/illustrations/topic-08.webp',
    'skyed_lobby/site/assets/illustrations/topic-09.webp',
    'skyed_lobby/site/assets/illustrations/topic-10.webp',
    'docs/VISUAL-IDENTITY-v2.4.0.md',
    'scripts/Install-SkyED-ControlPanel-v2.4.0.ps1',
    'scripts/Start-SkyED-CourseHub-Integration-v2.4.0.ps1',
    'scripts/package_control_panel_v240.py',
    'scripts/validate_lobby_content_v240.py',
    'tests/test_visual_v240.py',
    'tests/test_install_v240.py',
    'skyed_lobby/tests/test_visual_browser_v240.py'
)
$properties = @($manifest.files.PSObject.Properties)
if ($properties.Count -ne $expectedMembers.Count) { throw 'SKYED_V240_MANIFEST_MEMBER_COUNT_INVALID' }
foreach ($property in $properties) {
    $relative = [string]$property.Name
    if ($expectedMembers -cnotcontains $relative -or $relative.Contains('..') -or $relative.Contains('\\')) {
        throw "SKYED_V240_UNEXPECTED_MEMBER: $relative"
    }
    $source = Join-Path $SourceRoot ($relative.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "SKYED_V240_MEMBER_MISSING: $relative" }
    $actual = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = [string]$property.Value
    if ($actual -ne $expected.ToLowerInvariant()) { throw "SKYED_V240_HASH_MISMATCH: $relative" }
}
Write-Host "SKYED_V240_MANIFEST=PASS members=$($properties.Count)"

# Preserve existing user-edited lobby.json: source updates must not reset drafts.
$contentPath = 'skyed_lobby/site/content/lobby.json'
$existingContent = Join-Path $ProjectRoot ($contentPath.Replace('/', '\'))
$hasContent = Test-Path -LiteralPath $existingContent -PathType Leaf
if ($hasContent) {
    # Native PowerShell 5.1 strips nested quotes in python -c arguments. Run
    # a real, hash-checked Python file instead; it handles UTF-8 / UTF-8 BOM,
    # validates the existing draft and NEVER edits it.
    $validator = Join-Path $SourceRoot 'scripts\validate_lobby_content_v240.py'
    & $py $validator $existingContent
    if ($LASTEXITCODE -ne 0) { throw 'SKYED_EXISTING_LOBBY_CONTENT_INVALID_NO_OVERWRITE' }
}

$backup = Join-Path $ProjectRoot ('backups\control-panel-v2.4.0-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$previous = @{}
$success = $false
$desktopLink = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SkyED Control Panel.lnk'
$menuFolder = Join-Path ([Environment]::GetFolderPath('Programs')) 'Sky Education'
$menuLink = Join-Path $menuFolder 'SkyED Control Panel.lnk'
$links = @()
if (-not $SkipShortcuts) { $links = @($desktopLink, $menuLink) }
$oldLink = @{}

try {
    foreach ($property in $properties) {
        $relative = [string]$property.Name
        if ($relative -eq $contentPath -and $hasContent) { continue }
        if ($relative -match '^(docs/)') { continue }  # Documentation remains in release archive.
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
    Push-Location $ProjectRoot
    try {
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', 'offscreen', 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $fonts, 'Process')
        & $py -m py_compile 'scripts\validate_lobby_content_v240.py' 'skyed_control_panel.py' 'skyed_control\registry.py' 'skyed_control\lobby_workspace.py' 'skyed_lobby\scripts\control_server.py' 'skyed_control\integration_workspace.py' 'scripts\course_hub_integration.py' 'scripts\validate_lobby_content_v240.py'
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_PYTHON_COMPILE_FAILED' }
        & $py 'skyed_control_panel.py' --smoke-test
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_QT_STARTUP_FAILED' }
        & $py -m unittest discover -s skyed_lobby\tests -p 'test_control_lobby.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_LOCAL_SERVER_TESTS_FAILED' }
        & $py -m unittest discover -s tests -p 'test_course_hub_integration.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_INTEGRATION_TESTS_FAILED' }
        & $py -m unittest discover -s tests -p 'test_pilot_route_reconciliation.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_PILOT_LINK_INTEGRATION_TESTS_FAILED' }
        & $py -m unittest discover -s tests -p 'test_course_hub_integration_qt.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_INTEGRATION_QT_TESTS_FAILED' }
        & $py -m unittest discover -s tests -p 'test_install_v233.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_INSTALLER_VALIDATION_TESTS_FAILED' }
        & $py -m unittest discover -s tests -p 'test_visual_v240.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_VISUAL_SOURCE_GATE_FAILED' }
        & $py -m unittest discover -s tests -p 'test_install_v240.py' -q
        if ($LASTEXITCODE -ne 0) { throw 'SKYED_V240_REPRODUCIBLE_PACKAGE_GATE_FAILED' }
    } finally {
        Pop-Location
        [Environment]::SetEnvironmentVariable('QT_QPA_PLATFORM', $oldPlatform, 'Process')
        [Environment]::SetEnvironmentVariable('QT_QPA_FONTDIR', $oldFonts, 'Process')
    }
    Write-Host 'SKYED_V240_LOCAL_QA=PASS'

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
    if ($links.Count -gt 0) {
        $shell = New-Object -ComObject WScript.Shell
        New-Item -ItemType Directory -Path $menuFolder -Force | Out-Null
    }
    foreach ($linkPath in $links) {
        $shortcut = $shell.CreateShortcut($linkPath)
        $shortcut.TargetPath = $pyw
        $shortcut.Arguments = '"' + (Join-Path $ProjectRoot 'skyed_control_panel.py') + '"'
        $shortcut.WorkingDirectory = $ProjectRoot
        $shortcut.IconLocation = $icon
        $shortcut.Description = 'SkyED Control Panel 2.4.0 - Lobby Designer'
        $shortcut.Save()
        Write-Host "SKYED_V240_SHORTCUT=$linkPath"
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
        Write-Warning "SKYED_V240_INSTALL=ROLLED_BACK backups=$backup"
    }
}
Write-Host "SKYED_V240_INSTALL=PASS root=$ProjectRoot"
Write-Host 'LOBBY_DESIGNER=INTEGRATED BRIGHT_VISUALS=LIVE_LOCAL_PREVIEW COURSE_HUB_INTEGRATION=STAGE_ONLY'
Write-Host 'Existing lobby.json preserved. Integration staging requires authoritative current site capture; no remote writes occur.'
