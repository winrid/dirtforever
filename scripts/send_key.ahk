#Requires AutoHotkey v2.0
#Include C:\Users\winrid\Downloads\AutoHotInterception\AHK v2\Lib\AutoHotInterception.ahk

; Usage: send_key.ahk <keyName> [count] [delayMs]
;   keyName  — AHK key name (Enter, Escape, F4, Right, Down, Up, Left, x, etc.)
;   count    — number of presses (default 1)
;   delayMs  — ms to sleep after each press (default 900)

if A_Args.Length < 1 {
    ExitApp 2
}

keyName := A_Args[1]
count   := A_Args.Length >= 2 ? Integer(A_Args[2]) : 1
delayMs := A_Args.Length >= 3 ? Integer(A_Args[3]) : 900

gameWindow := "ahk_exe dirtrally2.exe"
SetTitleMatchMode 2

if !WinExist(gameWindow) {
    ExitApp 3
}
WinActivate gameWindow
WinWaitActive gameWindow, , 5
Sleep 300

AHI := AutoHotInterception()
keyboardIds := [1, 2, 3, 4, 5, 6]
sc := GetKeySC(keyName)

Loop count {
    for keyboardId in keyboardIds {
        AHI.SendKeyEvent(keyboardId, sc, 1)
    }
    Sleep 60
    for keyboardId in keyboardIds {
        AHI.SendKeyEvent(keyboardId, sc, 0)
    }
    if A_Index < count {
        Sleep delayMs
    }
}

ExitApp 0
