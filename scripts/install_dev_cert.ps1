param(
    [string]$CertPath = ".\runtime\certs\dr2server-cert.pem"
)

$ErrorActionPreference = "Stop"
$candidate = $CertPath
if (-not [System.IO.Path]::IsPathRooted($candidate)) {
    $candidate = Join-Path (Get-Location) $candidate
}
$resolved = Resolve-Path -LiteralPath $candidate
Import-Certificate -FilePath $resolved.Path -CertStoreLocation "Cert:\CurrentUser\Root" | Out-Null
Write-Host "Installed certificate into CurrentUser\\Root: $($resolved.Path)"
