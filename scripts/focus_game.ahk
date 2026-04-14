#Requires AutoHotkey v2.0

gameWindow := "ahk_exe dirtrally2.exe"
SetTitleMatchMode 2

if !WinExist(gameWindow) {
    ExitApp 3
}

; Release Windows foreground lock by tapping Alt, then activate.
Send "{Alt down}"
Sleep 30
Send "{Alt up}"
Sleep 30

WinActivate gameWindow
WinWaitActive gameWindow, , 3

; Force window to top z-order.
try WinMoveTop gameWindow
Sleep 150
ExitApp 0
