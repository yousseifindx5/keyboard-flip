@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Keyboard Flip - build installer
echo ============================================
echo   Keyboard Flip - building KeyboardFlip_Setup.exe
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found.
  echo Install Python 3.10 or newer from python.org and tick "Add python.exe to PATH", then run this again.
  goto :fail
)

echo [1/4] Installing build tools...
python -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo.
echo [2/4] Preparing the icon...
python make_icon.py
if errorlevel 1 goto :fail

echo.
echo [3/4] Building KeyboardFlip.exe...
python -m PyInstaller --noconfirm --clean --windowed --name KeyboardFlip --icon assets\icon.ico --add-data "assets;assets" --collect-all customtkinter --hidden-import pystray._win32 --hidden-import PIL._tkinter_finder main.py
if errorlevel 1 goto :fail

echo.
echo [4/4] Creating the installer...
call :find_iscc
if not defined ISCC (
  echo Inno Setup was not found - installing it with winget...
  winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
  call :find_iscc
)
if not defined ISCC (
  echo.
  echo Could not find Inno Setup. Install it from https://jrsoftware.org/isdl.php and run this file again.
  echo The program itself is already built in: dist\KeyboardFlip\KeyboardFlip.exe
  goto :fail
)
"%ISCC%" installer.iss
if errorlevel 1 goto :fail

echo.
echo ============================================
echo   DONE
echo   Your installer: installer_output\KeyboardFlip_Setup.exe
echo ============================================
explorer installer_output
pause
exit /b 0

:find_iscc
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0

:fail
echo.
echo Something went wrong - see the messages above.
pause
exit /b 1
