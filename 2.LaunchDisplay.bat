@echo off

"C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\ChromeKiosk" --kiosk --autoplay-policy=no-user-gesture-required --no-first-run --disable-infobars --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required http://10.77.235.225:5000/display
