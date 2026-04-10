#Requires AutoHotkey v2.0
#Include C:\Users\winrid\Downloads\AutoHotInterception\AHK v2\Lib\AutoHotInterception.ahk

if A_Args.Length < 1 {
    MsgBox "Usage: dr2_control.ahk <action>"
    ExitApp 2
}

action := A_Args[1]
gameExe := "F:\Steam\steamapps\common\DiRT Rally 2.0\dirtrally2.exe"
gameWindow := "ahk_exe dirtrally2.exe"
AHI := AutoHotInterception()
keyboardIds := [1, 2, 3, 4, 5, 6]

SetTitleMatchMode 2

LaunchGame() {
    global gameExe
    if !ProcessExist("dirtrally2.exe") {
        Run gameExe
        Sleep 30000
    }
}

FocusGame() {
    global gameWindow
    if WinExist(gameWindow) {
        WinActivate gameWindow
        WinWaitActive gameWindow, , 5
        Sleep 500
        return true
    }
    return false
}

PressKey(keyName, delayMs := 900) {
    global AHI, keyboardIds
    if !FocusGame() {
        ExitApp 5
    }
    sc := GetKeySC(keyName)
    for keyboardId in keyboardIds {
        AHI.SendKeyEvent(keyboardId, sc, 1)
    }
    Sleep 60
    for keyboardId in keyboardIds {
        AHI.SendKeyEvent(keyboardId, sc, 0)
    }
    Sleep delayMs
}

DriveStartScreen() {
    Loop 8 {
        PressKey("Enter", 3000)
    }
}

DriveEvents() {
    PressKey("Enter", 8000)
}

DriveClubs() {
    ; Back out aggressively from wherever we are to reach main menu
    Loop 6 {
        PressKey("Escape", 1200)
    }
    Sleep 2000
    ; Open the top navigation menu
    PressKey("F4", 2000)
    ; Navigate: Home > My Team > Clubs
    PressKey("Right", 1200)
    PressKey("Right", 1200)
    PressKey("Down", 1200)
    PressKey("Enter", 8000)
}

DriveFreePlay() {
    PressKey("F4", 1200)
    PressKey("Right", 1000)
    PressKey("Right", 1000)
    PressKey("Enter", 1200)
    PressKey("Enter", 1200)
    PressKey("Down", 700)
    PressKey("Down", 700)
    PressKey("Enter", 1200)
    PressKey("Enter", 30000)
    PressKey("Enter", 1500)
}

LaunchGame()
if !FocusGame() {
    MsgBox "Could not find a DiRT Rally 2.0 window."
    ExitApp 3
}

switch action {
    case "start":
        DriveStartScreen()
    case "events":
        DriveStartScreen()
        DriveEvents()
    case "clubs":
        ; Use 7 Enter presses (not 8) to reach main menu without selecting Events
        Loop 7 {
            PressKey("Enter", 3000)
        }
        ; Wait for main menu to settle
        Sleep 5000
        DriveClubs()
    case "freeplay":
        DriveStartScreen()
        DriveFreePlay()
    default:
        MsgBox "Unknown action: " action
        ExitApp 4
}

ExitApp 0
