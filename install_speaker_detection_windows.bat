@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 py -3 -m venv .venv
 if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r requirements_diarization.txt
if errorlevel 1 goto failed
echo Speaker detection dependencies installed.
pause
exit /b 0
:failed
echo Installation failed. Check Python and the message above.
pause
exit /b 1
