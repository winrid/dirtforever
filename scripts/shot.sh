#!/bin/bash
# Usage: shot.sh <name>  — activates DR2 window, screenshots to runtime/discovery/<name>.png
set -e
name="${1:-shot}"
dir="C:/Users/winrid/dr2server/runtime/discovery"
mkdir -p "$dir"

powershell -NoProfile -Command "
Add-Type -Name W -Namespace Win -MemberDefinition '
  [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int n);
';
\$p = Get-Process dirtrally2 -ErrorAction SilentlyContinue
if (\$p) {
  [Win.W]::ShowWindow(\$p.MainWindowHandle, 9) | Out-Null
  [Win.W]::SetForegroundWindow(\$p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 400
}
" >/dev/null

"C:/Users/winrid/Downloads/nircmd-x64/nircmd.exe" savescreenshotfull "$dir/$name.png"
echo "$dir/$name.png"
