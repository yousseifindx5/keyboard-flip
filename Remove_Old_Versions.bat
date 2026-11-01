@echo off
setlocal EnableExtensions
title Keyboard Flip - remove old versions
echo This removes leftovers of OLD Keyboard Flip versions (the Python-script versions).
echo It does NOT touch an installed Keyboard Flip (use Settings ^> Apps to uninstall that).
echo.

echo [1/3] Stopping old copies that are still running...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'keyboard_flip\.py|KeyboardFlip.*main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
taskkill /F /IM KeyboardFlip.exe >nul 2>&1

echo [2/3] Removing the old "start with Windows" entry...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v KeyboardFlip /f >nul 2>&1

echo [3/3] Old settings
choice /C YN /N /M "Also delete the old settings in %%APPDATA%%\KeyboardFlip ? [Y/N] (N keeps them, they work with the new version) "
if errorlevel 2 goto :keep
rmdir /S /Q "%APPDATA%\KeyboardFlip" >nul 2>&1
echo Settings deleted.
goto :done
:keep
echo Settings kept.
:done
echo.
echo Finished. Last step: delete the old KeyboardFlip folder(s) and keyboard_flip.py yourself
echo (they were never installed, so they are just normal files - e.g. in Downloads).
pause
