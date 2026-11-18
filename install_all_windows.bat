@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_windows.ps1"
if errorlevel 1 (
  echo Setup stopped. Read the error above and run this file again.
  pause
  exit /b 1
)
call "%~dp0run_windows.bat"
