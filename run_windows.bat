@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Python 3.11 or later is required.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe app.py
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Application setup or launch failed. Read the message above.
pause
exit /b 1
