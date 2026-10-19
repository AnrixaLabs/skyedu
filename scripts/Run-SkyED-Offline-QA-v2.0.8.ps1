<#
.SYNOPSIS
  Stage B: offline smoke + genuine package regression tests, without publishing.

.DESCRIPTION
  Creates a fresh clone under Downloads unless -RepoRoot is provided.
  Never writes to the user's PyCharm project or WordPress production.
  Uses a separate virtual environment and exports an evidence ZIP.

.EXAMPLE
  .\Run-SkyED-Offline-QA-v2.0.8.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$ReportRoot = '',
    [switch]$SkipDependencyInstallation
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/AnrixaLabs/skyedu.git'
$ExpectedBranch = 'feature/homework-automation-v2'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $ReportRoot) {
    $ReportRoot = Join-Path (Join-Path $env:USERPROFILE 'Downloads') "SkyED-Offline-QA-$Stamp"
}
if (Test-Path -LiteralPath $ReportRoot) {
    throw "Refusing to overwrite previous QA evidence: $ReportRoot"
}
New-Item -ItemType Directory -Path $ReportRoot -Force | Out-Null
$Evidence = Join-Path $ReportRoot 'evidence'
New-Item -ItemType Directory -Path $Evidence -Force | Out-Null
$Results = [ordered]@{
    schema = 'skyed.qa.v2.0.8'
    read_only_production = $true
    original_windows_project_untouched = $true
    expected_branch = $ExpectedBranch
    started_local = (Get-Date).ToString('o')
    checks = [ordered]@{}
}
function Check-Exit([string]$Label, [int]$Code) {
    $Results.checks[$Label] = if ($Code -eq 0) { 'PASS' } else { "FAIL ($Code)" }
    if ($Code -ne 0) { throw "$Label exited $Code" }
}
function Run-Python([string]$Label, [string[]]$CommandArgs, [string]$LogName) {
    $path = Join-Path $Evidence $LogName
    # Native Python writes test output to stderr even when tests pass.
    # PS 5.1 can turn native stderr into terminating errors when preference=Stop.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $script:Python @CommandArgs *> $path
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    Check-Exit $Label $code
}
try {
    Write-Host '============================================================'
    Write-Host ' SKYED OFFLINE QA v2.0.8'
    Write-Host '============================================================'
    Write-Host 'NO_WORDPRESS_WRITE=true NO_DNS_WRITE=true NO_PRODUCTION_DEPLOY=true'
    if (-not $RepoRoot) {
        $RepoRoot = Join-Path $ReportRoot 'skyedu'
        & git clone --branch $ExpectedBranch --single-branch --depth 1 $RepoUrl $RepoRoot
        Check-Exit 'git_clone' $LASTEXITCODE
    }
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot -ErrorAction Stop).ProviderPath
    $GitTopLines = @(& git -C $RepoRoot rev-parse --show-toplevel)
    if ($LASTEXITCODE -ne 0 -or $GitTopLines.Count -ne 1) {
        throw "Git failed to determine checkout root: $RepoRoot"
    }
    # Git for Windows emits C:/... while Resolve-Path emits C:\\... .
    # Compare *resolved filesystem paths*, case-insensitively, not raw strings.
    $GitTop = [string]$GitTopLines[0]
    try {
        $ResolvedGitTop = (Resolve-Path -LiteralPath $GitTop -ErrorAction Stop).ProviderPath
    } catch {
        throw "Git returned an invalid checkout root: $GitTop"
    }
    $ExpectedRoot = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd([char]92, [char]47)
    $ReportedRoot = [System.IO.Path]::GetFullPath($ResolvedGitTop).TrimEnd([char]92, [char]47)
    if (-not [string]::Equals($ExpectedRoot, $ReportedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Wrong repository root. Expected=$ExpectedRoot GitReported=$ReportedRoot"
    }
    $Results.checks.git_root = 'PASS'
    $CurrentBranch = (& git -C $RepoRoot branch --show-current).Trim()
    if ($CurrentBranch -ne $ExpectedBranch) {
        throw "Wrong branch $CurrentBranch, expected $ExpectedBranch"
    }
    $Head = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $Results.commit = $Head
    $Results.repository = $RepoRoot
    Set-Content -LiteralPath (Join-Path $Evidence 'commit.txt') -Value $Head -Encoding UTF8
    $Venv = Join-Path $ReportRoot 'qa-venv'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $Venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $Venv
    } else { throw 'Python 3 is required.' }
    Check-Exit 'qa_venv_creation' $LASTEXITCODE
    $script:Python = Join-Path $Venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $script:Python)) { throw 'Virtualenv Python not found.' }
    if (-not $SkipDependencyInstallation) {
        $Packages = @('python-dotenv>=1,<2', 'requests>=2.31,<3', 'Pillow>=10,<13', 'numpy>=1.26,<3')
        $PipLog = Join-Path $Evidence 'dependencies.log'
        # Preserve pip errors in the evidence instead of discarding them.
        $previousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $script:Python -m pip install @Packages *> $PipLog
            $pipExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        Check-Exit 'minimum_dependencies' $pipExit
    } else {
        $Results.checks.minimum_dependencies = 'SKIPPED_BY_USER'
    }
    Push-Location $RepoRoot
    try {
        Run-Python 'python_source_compile' @('-m','compileall','-q','skyed','scripts','run_pipeline.py','pyside_gui.py','tests') 'compile.log'
        Run-Python 'source_integrity' @('scripts/verify_repo_integrity.py','--repo','.','--json',(Join-Path $Evidence 'integrity.json')) 'integrity.log'
        Run-Python 'generator_cli' @('run_pipeline.py','--help') 'generator-cli-help.txt'
        Run-Python 'unit_tests' @('-m','unittest','discover','-s','tests','-v') 'unit-tests.log'
        Run-Python 'four_theme_dry_run' @('scripts/smoke_generator_offline.py','--repo','.','--report',(Join-Path $Evidence 'smoke-report.json')) 'smoke.log'
    } finally {
        Pop-Location
    }
    if (Get-Command php -ErrorAction SilentlyContinue) {
        & php -l (Join-Path $RepoRoot 'wp_plugin\skyed-lesson-renderer\skyed-lesson-renderer.php') |
            Out-File -LiteralPath (Join-Path $Evidence 'php-lint.log') -Encoding UTF8
        Check-Exit 'php_lint' $LASTEXITCODE
    } else {
        $Results.checks.php_lint = 'UNVERIFIED_PHP_CLI_MISSING'
    }
    $Results.status = 'OFFLINE_QA_PASS'
}
catch {
    $Results.status = 'BLOCKED'
    $Results.error = $_.Exception.Message
    Write-Host "[BLOCKED] $($Results.error)"
}
finally {
    $Results.finished_local = (Get-Date).ToString('o')
    $ReportFile = Join-Path $Evidence 'results.json'
    $Results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportFile -Encoding UTF8
    $ZipPath = Join-Path $ReportRoot 'SkyED-Offline-QA-Evidence.zip'
    Compress-Archive -Path (Join-Path $Evidence '*') -DestinationPath $ZipPath -CompressionLevel Optimal
    $ZipHash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash
    Write-Host "EVIDENCE_ZIP=$ZipPath"
    Write-Host "EVIDENCE_SHA256=$ZipHash"
    Write-Host "OFFLINE_QA_RESULT=$($Results.status)"
}
if ($Results.status -ne 'OFFLINE_QA_PASS') { exit 2 }
exit 0
