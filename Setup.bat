@echo off
cd /d "%~dp0"
py -3.11 --version >nul 2>&1 || (winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements & echo Reopen Setup.bat after installation & pause & exit /b 1)
if not exist .venv\Scripts\python.exe py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install PySide6 imageio-ffmpeg faster-whisper || exit /b 1
pause
