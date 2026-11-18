@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install "rembg[cpu]"
if errorlevel 1 goto failed
echo Background removal is ready. The model downloads on first use.
pause
exit /b 0
:failed
echo Installation failed. Read the message above.
pause
exit /b 1
