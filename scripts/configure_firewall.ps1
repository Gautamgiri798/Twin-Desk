<#
.SYNOPSIS
    DualDesk Windows Defender Firewall Configuration & LAN Rule Diagnostic Script

.DESCRIPTION
    Checks, configures, or removes inbound firewall rules for DualDesk:
      - UDP 53891 : Multicast / Broadcast LAN Discovery Beacon
      - TCP 53892 : Authenticated TLS Control Channel & Handshake
      - TCP 53893 : Low-Latency TLS Video/Audio Streaming Channel

.PARAMETER DryRun
    Simulates rule creation and reports port status without modifying firewall rules.

.PARAMETER CheckOnly
    Only checks current firewall rules for DualDesk ports without modifying rules.

.PARAMETER Remove
    Removes all DualDesk inbound firewall rules.

.PARAMETER DiscoveryPort
    UDP Discovery port (default: 53891).

.PARAMETER ControlPort
    TCP Control channel port (default: 53892).

.PARAMETER MediaPort
    TCP Media streaming port (default: 53893).
#>

[CmdletBinding()]
param (
    [switch]$DryRun,
    [switch]$CheckOnly,
    [switch]$Remove,
    [int]$DiscoveryPort = 53891,
    [int]$ControlPort = 53892,
    [int]$MediaPort = 53893
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param ([string]$Msg)
    Write-Host "[DualDesk Firewall] $Msg" -ForegroundColor Cyan
}

function Write-Success {
    param ([string]$Msg)
    Write-Host "[DualDesk Firewall] [OK] $Msg" -ForegroundColor Green
}

function Write-WarnMessage {
    param ([string]$Msg)
    Write-Host "[DualDesk Firewall] [WARN] $Msg" -ForegroundColor Yellow
}

function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Info "Evaluating Windows Firewall configuration for DualDesk..."
Write-Host "  Discovery Port (UDP) : $DiscoveryPort"
Write-Host "  Control Port   (TCP) : $ControlPort"
Write-Host "  Media Port     (TCP) : $MediaPort"

$isAdmin = Test-Admin

if ($Remove) {
    if (-not $isAdmin -and -not $DryRun) {
        Write-Error "Administrative privileges are required to remove firewall rules. Please run in an elevated PowerShell session."
        exit 1
    }
    if ($DryRun) {
        Write-Info "[DRY-RUN] Would remove inbound rules: DualDesk-Discovery-In, DualDesk-Control-In, DualDesk-Media-In."
        exit 0
    }
    Write-Info "Removing DualDesk firewall rules..."
    try {
        Remove-NetFirewallRule -DisplayName "DualDesk*" -ErrorAction SilentlyContinue
        Write-Success "DualDesk firewall rules removed successfully."
    } catch {
        netsh advfirewall firewall delete rule name="DualDesk-Discovery-In" | Out-Null
        netsh advfirewall firewall delete rule name="DualDesk-Control-In" | Out-Null
        netsh advfirewall firewall delete rule name="DualDesk-Media-In" | Out-Null
        Write-Success "DualDesk firewall rules removed via netsh."
    }
    exit 0
}

# Check existing rules
$rules = @(
    @{ Name = "DualDesk-Discovery-In"; Protocol = "UDP"; Port = $DiscoveryPort; Description = "DualDesk LAN Peer Discovery Beacon" },
    @{ Name = "DualDesk-Control-In"; Protocol = "TCP"; Port = $ControlPort; Description = "DualDesk Authenticated TLS Control Channel" },
    @{ Name = "DualDesk-Media-In"; Protocol = "TCP"; Port = $MediaPort; Description = "DualDesk Encrypted Media Streaming" }
)

$missingRules = @()

foreach ($r in $rules) {
    $existing = $null
    try {
        $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    } catch {
        $existing = $null
    }

    if ($existing) {
        Write-Success "Found existing rule: $($r.Name) ($($r.Protocol) $($r.Port))"
    } else {
        Write-WarnMessage "Missing rule: $($r.Name) ($($r.Protocol) $($r.Port))"
        $missingRules += $r
    }
}

if ($CheckOnly) {
    if ($missingRules.Count -eq 0) {
        Write-Success "All required DualDesk ports are allowed in Windows Firewall."
        exit 0
    } else {
        Write-WarnMessage "$($missingRules.Count) firewall rule(s) are missing."
        exit 0
    }
}

if ($missingRules.Count -eq 0) {
    Write-Success "Firewall is already fully configured for DualDesk. No changes required."
    exit 0
}

if ($DryRun) {
    Write-Info "[DRY-RUN] Would create the following inbound firewall rules:"
    foreach ($m in $missingRules) {
        Write-Host "  + Allow Inbound $($m.Protocol) port $($m.Port) ($($m.Name))"
    }
    exit 0
}

if (-not $isAdmin) {
    Write-Error "Administrative privileges are required to create firewall rules. Please run in an elevated PowerShell session."
    exit 1
}

Write-Info "Creating missing inbound firewall rules..."
foreach ($m in $missingRules) {
    try {
        New-NetFirewallRule -DisplayName $m.Name `
            -Direction Inbound `
            -Action Allow `
            -Protocol $m.Protocol `
            -LocalPort $m.Port `
            -Description $m.Description `
            -Profile Any `
            -Enabled True | Out-Null
        Write-Success "Created rule: $($m.Name) ($($m.Protocol) $($m.Port))"
    } catch {
        netsh advfirewall firewall add rule name="$($m.Name)" dir=in action=allow protocol="$($m.Protocol)" localport="$($m.Port)" description="$($m.Description)" | Out-Null
        Write-Success "Created rule via netsh: $($m.Name) ($($m.Protocol) $($m.Port))"
    }
}

Write-Success "Firewall configuration completed successfully."
exit 0
