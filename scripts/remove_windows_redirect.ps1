param()

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Restart-Elevated {
    $argList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath)
    )

    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList | Out-Null
    exit 0
}

if (-not (Test-IsAdministrator)) {
    Write-Host "Requesting administrator access to remove hosts entries..."
    Restart-Elevated
}

$hostsPath = Join-Path $env:WINDIR "System32\drivers\etc\hosts"
$beginMarker = "# BEGIN DR2 COMMUNITY SERVER"
$endMarker = "# END DR2 COMMUNITY SERVER"

if (-not (Test-Path $hostsPath)) {
    Write-Host "Hosts file not found."
    exit 0
}

$existing = Get-Content -LiteralPath $hostsPath -Raw
if ($null -eq $existing) {
    $existing = ""
}
$escapedBegin = [regex]::Escape($beginMarker)
$escapedEnd = [regex]::Escape($endMarker)
$pattern = "(?ms)^$escapedBegin\r?\n.*?^$escapedEnd\r?\n?"
$cleaned = [regex]::Replace($existing, $pattern, "")
$cleaned = $cleaned.TrimEnd("`r", "`n")

if ([string]::IsNullOrWhiteSpace($cleaned)) {
    $cleaned = ""
} else {
    $cleaned += "`r`n"
}

Set-Content -LiteralPath $hostsPath -Value $cleaned -Encoding ASCII
Write-Host "Removed DR2 community server hosts entries."
