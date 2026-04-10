#Requires AutoHotkey v2.0
#Include C:\Users\winrid\Downloads\AutoHotInterception\AHK v2\Lib\AutoHotInterception.ahk

AHI := AutoHotInterception()
devices := AHI.GetDeviceList()

output := ""
for id, device in devices {
    kind := device.IsMouse ? "mouse" : "keyboard"
    output .= id " " kind " VID=0x" Format("{:04X}", device.VID) " PID=0x" Format("{:04X}", device.PID) " HANDLE=" device.Handle "`n"
}

if FileExist(A_ScriptDir "\ahi_devices.txt")
    FileDelete A_ScriptDir "\ahi_devices.txt"
FileAppend output, A_ScriptDir "\ahi_devices.txt", "UTF-8"
ExitApp
