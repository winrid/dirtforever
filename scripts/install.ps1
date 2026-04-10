<#
.SYNOPSIS
    DirtForever game server installer for Windows.
.DESCRIPTION
    Sets up the DirtForever game server on a player's PC:
    - Checks for Python 3.9+
    - Creates %APPDATA%\DirtForever\
    - Generates and trusts the TLS certificate
    - Adds hosts file redirects
    - Prompts for the game token from dirtforever.net/dashboard
    - Saves config.json
    - Creates a desktop shortcut

    Safe to run multiple times (idempotent).
#>
param(
    [string]$ServerDir = $PSScriptRoot | Split-Path -Parent
)

$ErrorActionPreference = "Stop"

# ── Admin check / self-elevation ──────────────────────────────────────────────

function Test-IsAdministrator {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    Write-Host "Requesting administrator privileges (required for hosts file and cert trust)..."
    $argList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath),
        "-ServerDir", ('"{0}"' -f $ServerDir)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList
    exit 0
}

Write-Host ""
Write-Host "======================================================"
Write-Host "  DirtForever Game Server Installer"
Write-Host "======================================================"
Write-Host ""

# ── Step 1: Check Python 3.9+ ─────────────────────────────────────────────────

Write-Host "[1/7] Checking Python installation..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 9)) {
                $pythonCmd = $cmd
                Write-Host "    Found: $ver"
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "ERROR: Python 3.9 or newer is required but was not found." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 2: Create %APPDATA%\DirtForever\ ────────────────────────────────────

Write-Host "[2/7] Creating config directory..."

$configDir = Join-Path $env:APPDATA "DirtForever"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    Write-Host "    Created: $configDir"
} else {
    Write-Host "    Already exists: $configDir"
}

# ── Step 3: Generate TLS certificate ─────────────────────────────────────────

Write-Host "[3/7] Generating TLS certificate..."

$certScript = Join-Path $ServerDir "scripts\generate_dev_cert.py"
$certPath   = Join-Path $ServerDir "runtime\certs\dr2server-cert.pem"
$keyPath    = Join-Path $ServerDir "runtime\certs\dr2server-key.pem"

if (-not (Test-Path $certScript)) {
    Write-Host "    ERROR: Cannot find $certScript" -ForegroundColor Red
    Write-Host "    Make sure you are running this from the dr2server directory." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

try {
    & $pythonCmd $certScript --cert $certPath --key $keyPath
    Write-Host "    Certificate: $certPath"
    Write-Host "    Key:         $keyPath"
} catch {
    Write-Host "    ERROR generating certificate: $_" -ForegroundColor Red
    Write-Host "    Make sure the 'cryptography' package is installed: $pythonCmd -m pip install cryptography" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 4: Trust the certificate ────────────────────────────────────────────

Write-Host "[4/7] Installing certificate into trusted root store..."

$installCertScript = Join-Path $ServerDir "scripts\install_dev_cert.ps1"
if (-not (Test-Path $installCertScript)) {
    Write-Host "    ERROR: Cannot find $installCertScript" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

try {
    & powershell.exe -ExecutionPolicy Bypass -File $installCertScript -CertPath $certPath
    Write-Host "    Certificate trusted."
} catch {
    Write-Host "    ERROR trusting certificate: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 5: Add hosts file redirects ─────────────────────────────────────────

Write-Host "[5/7] Configuring hosts file redirects..."

$redirectScript = Join-Path $ServerDir "scripts\setup_windows_redirect.ps1"
if (-not (Test-Path $redirectScript)) {
    Write-Host "    ERROR: Cannot find $redirectScript" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

try {
    & powershell.exe -ExecutionPolicy Bypass -File $redirectScript -SkipCertificateNotice
    Write-Host "    Hosts file updated."
} catch {
    Write-Host "    ERROR updating hosts file: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 6: Prompt for game token ────────────────────────────────────────────

Write-Host "[6/7] Game token configuration..."
Write-Host ""

$configFile = Join-Path $configDir "config.json"
$existingToken = ""

if (Test-Path $configFile) {
    try {
        $existingCfg = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
        $existingToken = $existingCfg.api_token
    } catch { }
}

if ($existingToken -and $existingToken -match "^df_[0-9a-f]{32}$") {
    Write-Host "    Existing token found (ends in ...$(${existingToken}.Substring(${existingToken}.Length - 8)))."
    $changeToken = Read-Host "    Enter a new token to replace it, or press Enter to keep existing"
    if ($changeToken.Trim() -ne "") {
        $apiToken = $changeToken.Trim()
    } else {
        $apiToken = $existingToken
    }
} else {
    Write-Host "    Get your game token at: https://dirtforever.net/dashboard"
    Write-Host "    (Log in, scroll to 'Game Server Token', click Generate Token)"
    Write-Host ""
    $apiToken = Read-Host "    Enter your DirtForever game token (df_...)"
}

$apiToken = $apiToken.Trim()
if ($apiToken -notmatch "^df_[0-9a-f]{32}$") {
    Write-Host "    WARNING: Token does not look like a valid DirtForever token (expected df_ + 32 hex chars)." -ForegroundColor Yellow
    Write-Host "    Continuing anyway — you can edit $configFile later." -ForegroundColor Yellow
}

# ── Step 6b: Save config.json ─────────────────────────────────────────────────

$config = @{
    api_url   = "https://dirtforever.net"
    api_token = $apiToken
}
$config | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $configFile -Encoding UTF8
Write-Host "    Config saved: $configFile"

# ── Step 7: Create desktop shortcut ──────────────────────────────────────────

Write-Host "[7/7] Creating desktop shortcut..."

$desktopPath  = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "DirtForever Server.lnk"

# Find pythonw for the shortcut (run without a console window)
$pythonwCmd = $null
foreach ($cmd in @("pythonw", "pythonw3")) {
    try {
        $resolved = (Get-Command $cmd -ErrorAction SilentlyContinue)
        if ($resolved) { $pythonwCmd = $resolved.Source; break }
    } catch { }
}
if (-not $pythonwCmd) {
    # Fall back: replace python.exe with pythonw.exe in the same directory
    $pythonExe = (Get-Command $pythonCmd -ErrorAction SilentlyContinue)?.Source
    if ($pythonExe) {
        $candidate = Join-Path (Split-Path $pythonExe) "pythonw.exe"
        if (Test-Path $candidate) { $pythonwCmd = $candidate }
    }
}
if (-not $pythonwCmd) {
    $pythonwCmd = $pythonCmd  # last resort: use python (will show console)
}

$serverScript  = Join-Path $ServerDir "dr2server\__main__.py"
$shortcutArgs  = "`"$serverScript`" --ssl-cert `"$certPath`" --ssl-key `"$keyPath`""

$wsh      = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $pythonwCmd
$shortcut.Arguments        = $shortcutArgs
$shortcut.WorkingDirectory = $ServerDir
$shortcut.Description      = "DirtForever Game Server"
$shortcut.Save()

Write-Host "    Shortcut created: $shortcutPath"

# ── Done ──────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "======================================================"
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "======================================================"
Write-Host ""
Write-Host "To start the server, double-click 'DirtForever Server' on your Desktop."
Write-Host "Then launch DiRT Rally 2.0 — it will connect to your local server."
Write-Host ""
Write-Host "Your config is stored at:"
Write-Host "    $configFile"
Write-Host ""
Read-Host "Press Enter to close"
