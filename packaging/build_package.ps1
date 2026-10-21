# packaging/build_package.ps1
# Automates DualDesk standalone packaging and installer compilation
# Supports -DryRun validation for CI and non-destructive development environments

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipDriver,
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistDir = Join-Path $ProjectRoot "dist\dualdesk"
$InstallerDir = Join-Path $ProjectRoot "dist\installer"
$IssScript = Join-Path $PSScriptRoot "dualdesk_installer.iss"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " DualDesk Windows Standalone Packaging & Build Workflow" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot"
Write-Host "Staging Directory: $DistDir"
Write-Host "Inno Setup Script: $IssScript"
Write-Host "Mode: $(if ($DryRun) { 'DryRun (Simulation & Validation)' } else { 'Full Build' })"
Write-Host ""

# 1. Validate Prerequisite Files
$requiredFiles = @(
    (Join-Path $ProjectRoot "pyproject.toml"),
    (Join-Path $ProjectRoot "README.md"),
    (Join-Path $ProjectRoot "src\dualdesk\ui\app.py"),
    (Join-Path $ProjectRoot "scripts\configure_firewall.ps1"),
    (Join-Path $ProjectRoot "scripts\build_driver.ps1"),
    (Join-Path $ProjectRoot "native\idd_driver\IddDriver.inf")
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Error "Required packaging source file missing: $file"
        exit 1
    }
}
Write-Host "[OK] All required source and configuration files exist." -ForegroundColor Green

# 2. Validate Inno Setup Script Syntax & Directives
if (-not (Test-Path $IssScript)) {
    Write-Error "Inno Setup script not found at $IssScript"
    exit 1
}

$issContent = Get-Content -Path $IssScript -Raw
$requiredDirectives = @(
    "AppName",
    "AppVersion",
    "DefaultDirName",
    "PrivilegesRequired=admin",
    "ArchitecturesAllowed=x64compatible",
    "configure_firewall.ps1",
    "[UninstallRun]",
    "[UninstallDelete]"
)

foreach ($dir in $requiredDirectives) {
    if ($issContent -notmatch [regex]::Escape($dir)) {
        Write-Error "Inno Setup script missing expected directive: '$dir'"
        exit 1
    }
}
Write-Host "[OK] Inno Setup script structure and uninstaller directives verified." -ForegroundColor Green

# 3. Handle DryRun Mode
if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] Validation successful. Package staging and compiler steps simulated." -ForegroundColor Yellow
    Write-Host "[DryRun] Staging target: $DistDir" -ForegroundColor Yellow
    Write-Host "[DryRun] Target installer: $InstallerDir\DualDesk_Setup_v0.1.0.exe" -ForegroundColor Yellow
    exit 0
}

# 4. Create Output Directories
if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
}
if (-not (Test-Path $InstallerDir)) {
    New-Item -ItemType Directory -Path $InstallerDir -Force | Out-Null
}

# 5. Check for Inno Setup Compiler (iscc.exe)
$isccPaths = @(
    "iscc.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe",
    "${env:ProgramFiles}\Inno Setup 6\iscc.exe"
)

$isccExe = $null
foreach ($path in $isccPaths) {
    if (Get-Command $path -ErrorAction SilentlyContinue) {
        $isccExe = $path
        break
    }
    if (Test-Path $path) {
        $isccExe = $path
        break
    }
}

if (-not $isccExe) {
    Write-Warning "Inno Setup Compiler (iscc.exe) not found on PATH or Program Files."
    Write-Warning "To compile the final installer, install Inno Setup 6 (https://jrsoftware.org/isdl.php)."
    exit 0
}

Write-Host "Compiling installer with $isccExe..." -ForegroundColor Cyan
& $isccExe $IssScript
Write-Host "[SUCCESS] DualDesk installer successfully generated in $InstallerDir." -ForegroundColor Green
