<#
.SYNOPSIS
    DualDesk Native Windows IDD Driver Build, Test-Signing & Packaging Script

.DESCRIPTION
    Detects Visual Studio, MSBuild, CMake, Windows SDK, and Windows Driver Kit (WDK) tools.
    Compiles the native IddCx user-mode display driver (UMDF 2.x), packages driver binaries
    with INF manifests, creates/manages local test-signing certificates, and optionally
    installs the driver package on test systems.

.PARAMETER Configuration
    Build configuration: "Release" (default) or "Debug".

.PARAMETER Platform
    Target architecture: "x64" (default) or "ARM64".

.PARAMETER BuildOnly
    Only compile the driver binaries without creating certificates or signing.

.PARAMETER SignOnly
    Only sign existing built driver binaries without recompiling.

.PARAMETER Install
    Install the driver package on the local machine (requires Administrator and testsigning ON).

.PARAMETER DryRun
    Simulate and report toolchain paths without creating files, modifying certificates, or installing.

.PARAMETER CertSubject
    Subject name for self-signed code-signing test certificate.
#>

[CmdletBinding()]
param (
    [ValidateSet("Release", "Debug")]
    [string]$Configuration = "Release",

    [ValidateSet("x64", "ARM64")]
    [string]$Platform = "x64",

    [switch]$BuildOnly,
    [switch]$SignOnly,
    [switch]$Install,
    [switch]$DryRun,
    [string]$CertSubject = "CN=DualDesk Test Display Driver"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param ([string]$Message)
    Write-Host "`n[DualDesk Driver Build] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param ([string]$Message)
    Write-Host "[DualDesk Driver Build] [OK] $Message" -ForegroundColor Green
}

function Write-WarnMessage {
    param ([string]$Message)
    Write-Host "[DualDesk Driver Build] [WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrMessage {
    param ([string]$Message)
    Write-Host "[DualDesk Driver Build] [ERROR] $Message" -ForegroundColor Red
}

# 1. Resolve Project Paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$NativeDir = Join-Path $ProjectRoot "native"
$IddDriverDir = Join-Path $NativeDir "idd_driver"
$BuildDir = Join-Path $NativeDir "build"
$DistDir = Join-Path $NativeDir "dist"

Write-Step "Resolving project structure..."
Write-Host "  Project Root : $ProjectRoot"
Write-Host "  Native Source: $NativeDir"
Write-Host "  Driver Source: $IddDriverDir"
Write-Host "  Build Output : $BuildDir"
Write-Host "  Dist Output  : $DistDir"

# 2. Locate Visual Studio & Build Tools
Write-Step "Detecting Visual Studio & CMake..."
$VsWherePath = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$VsPath = $null
if (Test-Path $VsWherePath) {
    $VsPath = & $VsWherePath -latest -products * -property installationPath
}

if ($VsPath) {
    Write-Success "Found Visual Studio at: $VsPath"
} else {
    Write-WarnMessage "Visual Studio installation not detected via vswhere. Fallback to CMake in PATH."
}

$CMakeExe = Get-Command "cmake" -ErrorAction SilentlyContinue
if (-not $CMakeExe) {
    Write-ErrMessage "CMake is not installed or not found in system PATH. Please install CMake 3.20+."
    exit 1
}
Write-Success "Found CMake: $($CMakeExe.Source)"

# 3. Locate Windows Kits & WDK Tools
Write-Step "Detecting Windows Kits & Driver Tools (signtool, inf2cat, devcon)..."
$KitsRoot = "${env:ProgramFiles(x86)}\Windows Kits\10"
$SignToolPath = $null
$Inf2CatPath = $null
$DevConPath = $null

if (Test-Path $KitsRoot) {
    $BinFolder = Join-Path $KitsRoot "bin"
    if (Test-Path $BinFolder) {
        $SignTools = Get-ChildItem -Path $BinFolder -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*$Platform*" }
        if ($SignTools) {
            $SignToolPath = $SignTools[0].FullName
            Write-Success "Found signtool.exe: $SignToolPath"
        }

        $Inf2Cats = Get-ChildItem -Path $BinFolder -Recurse -Filter "Inf2Cat.exe" -ErrorAction SilentlyContinue
        if ($Inf2Cats) {
            $Inf2CatPath = $Inf2Cats[0].FullName
            Write-Success "Found Inf2Cat.exe: $Inf2CatPath"
        }

        $DevCons = Get-ChildItem -Path $BinFolder -Recurse -Filter "devcon.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*$Platform*" }
        if ($DevCons) {
            $DevConPath = $DevCons[0].FullName
            Write-Success "Found devcon.exe: $DevConPath"
        }
    }
}

if (-not $SignToolPath) {
    $cmdSign = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($cmdSign) { $SignToolPath = $cmdSign.Source }
}
if (-not $DevConPath) {
    $cmdDev = Get-Command "devcon.exe" -ErrorAction SilentlyContinue
    if ($cmdDev) { $DevConPath = $cmdDev.Source }
}

if (-not $SignToolPath) {
    Write-WarnMessage "signtool.exe not found in Windows Kits. Driver signing will be skipped unless tools are installed."
}

if ($DryRun) {
    Write-Step "[DRY RUN] Summary of planned actions:"
    Write-Host "  Mode         : Configuration=$Configuration, Platform=$Platform"
    Write-Host "  Compile      : $(if ($SignOnly) { 'Skip' } else { 'Execute CMake/MSBuild build in ' + $BuildDir })"
    Write-Host "  Sign         : $(if ($BuildOnly) { 'Skip' } else { 'Create/Sign test certificate and package in ' + $DistDir })"
    Write-Host "  Installation : $(if ($Install) { 'Execute devcon/pnputil installation' } else { 'Skip (install switch not supplied)' })"
    Write-Success "[DRY RUN] Completed successfully without filesystem or system changes."
    exit 0
}

# 4. Compilation Step
if (-not $SignOnly) {
    Write-Step "Building native driver binaries ($Configuration | $Platform)..."
    if (-not (Test-Path $BuildDir)) {
        New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
    }

    $Generator = "Visual Studio 17 2022"
    Write-Host "Configuring CMake project with generator '$Generator' ($Platform)..."
    & cmake -G $Generator -A $Platform -S $NativeDir -B $BuildDir
    if ($LASTEXITCODE -ne 0) {
        Write-ErrMessage "CMake configuration failed."
        exit $LASTEXITCODE
    }

    Write-Host "Compiling driver binaries ($Configuration)..."
    & cmake --build $BuildDir --config $Configuration
    if ($LASTEXITCODE -ne 0) {
        Write-ErrMessage "CMake build failed."
        exit $LASTEXITCODE
    }
    Write-Success "Native compilation succeeded."
}

# 5. Packaging & Signing Step
if (-not $BuildOnly) {
    Write-Step "Packaging driver distribution artifacts..."
    if (-not (Test-Path $DistDir)) {
        New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
    }

    # Locate compiled driver DLL
    $DllSearchPaths = @(
        (Join-Path $BuildDir "$Configuration\dualdesk_idd.dll"),
        (Join-Path $BuildDir "dualdesk_idd.dll"),
        (Join-Path $BuildDir "idd_driver\$Configuration\dualdesk_idd.dll")
    )
    $DriverDll = $DllSearchPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($DriverDll) {
        Copy-Item -Path $DriverDll -Destination (Join-Path $DistDir "dualdesk_idd.dll") -Force
        Write-Success "Copied dualdesk_idd.dll to dist."
    } else {
        Write-WarnMessage "Compiled dualdesk_idd.dll not found in standard build directories."
    }

    # Copy INF manifest
    $InfPath = Join-Path $IddDriverDir "IddDriver.inf"
    if (Test-Path $InfPath) {
        Copy-Item -Path $InfPath -Destination (Join-Path $DistDir "IddDriver.inf") -Force
        Write-Success "Copied IddDriver.inf to dist."
    }

    # Generate Security Catalog (.cat) if Inf2Cat is available
    if ($Inf2CatPath -and (Test-Path (Join-Path $DistDir "IddDriver.inf"))) {
        Write-Step "Generating driver security catalog via Inf2Cat..."
        $OsList = if ($Platform -eq "ARM64") { "10_ARM64,Server10_ARM64" } else { "10_X64,Server10_X64" }
        & $Inf2CatPath "/driver:$DistDir" "/os:$OsList"
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Catalog generated: IddDriver.cat"
        } else {
            Write-WarnMessage "Inf2Cat completed with warnings or error ($LASTEXITCODE)."
        }
    }

    # Test-Signing via PowerShell Certificate Provider / SignTool
    Write-Step "Managing test-signing certificate..."
    $Cert = Get-ChildItem -Path "Cert:\CurrentUser\My" -CodeSigningCert |
        Where-Object { $_.Subject -eq $CertSubject } | Select-Object -First 1

    if (-not $Cert) {
        Write-Host "Creating new local self-signed test code-signing certificate '$CertSubject'..."
        $Cert = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject $CertSubject `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -HashAlgorithm "SHA256" `
            -NotAfter (Get-Date).AddYears(5)
        Write-Success "Created test certificate with Thumbprint: $($Cert.Thumbprint)"
    } else {
        Write-Success "Using existing test certificate: $($Cert.Thumbprint)"
    }

    # Export public certificate (.cer)
    $CerPath = Join-Path $DistDir "DualDeskTestCert.cer"
    Export-Certificate -Cert $Cert -FilePath $CerPath -Force | Out-Null
    Write-Success "Exported public test certificate to: $CerPath"

    # Sign distribution files
    if ($SignToolPath) {
        Write-Step "Signing driver files using signtool.exe..."
        $FilesToSign = Get-ChildItem -Path $DistDir -Include "*.dll","*.cat" -Recurse
        foreach ($file in $FilesToSign) {
            & $SignToolPath sign /v /fd SHA256 /sha1 $($Cert.Thumbprint) /s "My" $file.FullName
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Signed $($file.Name)"
            } else {
                Write-WarnMessage "Failed to sign $($file.Name) with code $LASTEXITCODE."
            }
        }
    }
}

# 6. Installation Step (Optional, Requires Elevated Privileges)
if ($Install) {
    Write-Step "Verifying prerequisites for local driver installation..."

    # Check Administrator Privileges
    $IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $IsAdmin) {
        Write-ErrMessage "Driver installation requires elevated Administrator privileges. Please re-run PowerShell as Administrator."
        exit 1
    }

    # Check Test-Signing Status
    $BcdOutput = bcdedit.exe /enum "{current}" 2>&1 | Out-String
    $IsTestSigning = $BcdOutput -match "testsigning\s+Yes"
    if (-not $IsTestSigning) {
        Write-WarnMessage "Windows Test-Signing mode is currently DISABLED."
        Write-Host "  To install self-signed drivers, run in an Administrator command prompt:"
        Write-Host "    bcdedit.exe /set testsigning on"
        Write-Host "  and restart your computer before proceeding.`n"
        $ConfirmContinue = Read-Host "Proceed with installation attempt anyway? (y/N)"
        if ($ConfirmContinue -notmatch "^[yY]$") {
            Write-Host "Installation aborted by user."
            exit 0
        }
    } else {
        Write-Success "Windows Test-Signing mode is verified ON."
    }

    # Install Test Certificate into Trusted Root & Trusted Publishers
    $CerPath = Join-Path $DistDir "DualDeskTestCert.cer"
    if (Test-Path $CerPath) {
        Write-Host "Installing test certificate into TrustedPublisher and Root stores..."
        Import-Certificate -FilePath $CerPath -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" | Out-Null
        Import-Certificate -FilePath $CerPath -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null
        Write-Success "Test certificate installed into LocalMachine stores."
    }

    # Install Driver Package via PnPUtil
    $DistInf = Join-Path $DistDir "IddDriver.inf"
    if (Test-Path $DistInf) {
        Write-Step "Installing driver package via PnPUtil..."
        & pnputil.exe /add-driver $DistInf /install
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Driver package added to system driver store."
        } else {
            Write-WarnMessage "PnPUtil returned status code $LASTEXITCODE."
        }
    }

    # Create Virtual Display Device node via DevCon if available
    if ($DevConPath) {
        Write-Step "Creating virtual display device node via devcon.exe..."
        & $DevConPath install $DistInf "Root\DualDeskDisplay"
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Virtual display device created successfully: Root\DualDeskDisplay"
        } else {
            Write-WarnMessage "DevCon install exited with code $LASTEXITCODE."
        }
    } else {
        Write-Host "devcon.exe was not detected. If needed, create the device node using:"
        Write-Host "  devcon.exe install `"$DistInf`" Root\DualDeskDisplay"
    }
}

Write-Step "DualDesk Native Driver Build Workflow Completed."
Write-Host "Artifacts are ready in: $DistDir`n"
