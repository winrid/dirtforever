param(
    [string]$ServerIp = "127.0.0.1",
    [switch]$SkipCertificateNotice
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Restart-Elevated {
    $argList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath),
        "-ServerIp", ('"{0}"' -f $ServerIp)
    )

    if ($SkipCertificateNotice) {
        $argList += "-SkipCertificateNotice"
    }

    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList | Out-Null
    exit 0
}

if (-not (Test-IsAdministrator)) {
    Write-Host "Requesting administrator access to update hosts entries..."
    Restart-Elevated
}

$domains = @(
    "prod.egonet.codemasters.com",
    "qa.egonet.codemasters.com",
    "terms.codemasters.com",
    "aurora.codemasters.local"
)

$hostsPath = Join-Path $env:WINDIR "System32\drivers\etc\hosts"
$beginMarker = "# BEGIN DR2 COMMUNITY SERVER"
$endMarker = "# END DR2 COMMUNITY SERVER"

$existing = ""
if (Test-Path $hostsPath) {
    $existing = Get-Content -LiteralPath $hostsPath -Raw
}
if ($null -eq $existing) {
    $existing = ""
}

$escapedBegin = [regex]::Escape($beginMarker)
$escapedEnd = [regex]::Escape($endMarker)
$pattern = "(?ms)^$escapedBegin\r?\n.*?^$escapedEnd\r?\n?"
$cleaned = [regex]::Replace($existing, $pattern, "")
$cleaned = $cleaned.TrimEnd("`r", "`n")

$blockLines = @($beginMarker)
foreach ($domain in $domains) {
    $blockLines += "$ServerIp`t$domain"
}
$blockLines += $endMarker

$newContent = if ([string]::IsNullOrWhiteSpace($cleaned)) {
    ($blockLines -join "`r`n") + "`r`n"
} else {
    $cleaned + "`r`n`r`n" + ($blockLines -join "`r`n") + "`r`n"
}

Set-Content -LiteralPath $hostsPath -Value $newContent -Encoding ASCII
Write-Host "Updated hosts file: $hostsPath"
Write-Host "Redirected domains to $ServerIp"

if (-not $SkipCertificateNotice) {
    Write-Host ""
    Write-Host "Important:"
    Write-Host "The game likely uses HTTPS for these backends."
    Write-Host "DNS or hosts redirection alone is not enough if the client validates TLS certificates."
    Write-Host "You still need either:"
    Write-Host "  1. A trusted certificate for the redirected hostname, or"
    Write-Host "  2. A binary patch / proxy flow that bypasses certificate validation."
}
