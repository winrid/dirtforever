param(
    [ValidateSet("start", "events", "clubs", "freeplay")]
    [string]$Action = "events",
    [string]$ArtifactsDir = ".\runtime\gamebot"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactsRoot = Join-Path $repoRoot $ArtifactsDir
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $artifactsRoot $timestamp

$ahk = "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
$nircmd = "C:\Users\winrid\Downloads\nircmd-x64\nircmd.exe"
$tesseract = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$scriptPath = Join-Path $PSScriptRoot "dr2_control.ahk"
$screenshotPath = Join-Path $runDir "screen.png"
$ocrBasePath = Join-Path $runDir "screen_ocr"
$ocrTextPath = "$ocrBasePath.txt"
$metaPath = Join-Path $runDir "meta.json"

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

foreach ($required in @($ahk, $nircmd, $tesseract, $scriptPath)) {
    if (-not (Test-Path $required)) {
        throw "Missing required path: $required"
    }
}

& $ahk $scriptPath $Action
Start-Sleep -Seconds 3

& $nircmd win activate process dirtrally2.exe
Start-Sleep -Milliseconds 800
& $nircmd savescreenshotfull $screenshotPath
& $tesseract $screenshotPath $ocrBasePath --psm 6 | Out-Null

$ocrText = ""
if (Test-Path $ocrTextPath) {
    $ocrText = Get-Content $ocrTextPath -Raw
}

$meta = [ordered]@{
    action = $Action
    timestamp = $timestamp
    screenshot = $screenshotPath
    ocr_text = $ocrText
}

$meta | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $metaPath
$meta | ConvertTo-Json -Depth 4
