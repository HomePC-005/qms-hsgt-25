#Requires AutoHotkey v2.0+

; === Step 1: Run Flask server ===
Run "python app.py"
Sleep 5000  ; wait for server to start

; === Step 2: Run patient display script ===
Run "chrome.exe --user-data-dir=C:\ChromeKiosk --kiosk --autoplay-policy=no-user-gesture-required --no-first-run --disable-infobars --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required http://10.77.235.225:5000/display"
WinWaitActive "ahk_exe chrome.exe"

; Wait for Chrome window to be active
Sleep 1000
; Move window to second monitor (adjust X, Y, width, height as needed)
WinMove 1920, 0, 1920, 1080, "ahk_exe chrome.exe"
Sleep 1500

; === Step 3: Open Edge staff panel in app mode with custom profile ===
edgePath := "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
profileDir := "C:\Temp\EdgeKioskProfile"
profileName := "MyProfile"
url := "http://10.77.235.225:5000/"

Run '"' edgePath '" --app=' url ' --user-data-dir="' profileDir '" --profile-directory=' profileName

Sleep 1000

WinWaitActive "ahk_exe msedge.exe"
WinMove 0, 0, 1280, 800, "ahk_exe msedge.exe"
Sleep 500
WinMaximize "ahk_exe msedge.exe"