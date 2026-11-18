@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>&1
if errorlevel 1 (
 echo Git is required. Install Git for Windows first.
 pause
 exit /b 1
)
py -3.8 -c "import sys" >nul 2>&1
if errorlevel 1 (
 echo Python 3.8 x64 is required for SadTalker. Install it and rerun this file.
 pause
 exit /b 1
)
if not exist "tools\SadTalker\inference.py" git clone https://github.com/OpenTalker/SadTalker.git "tools\SadTalker"
if errorlevel 1 goto failed
if not exist "tools\SadTalker\.venv\Scripts\python.exe" py -3.8 -m venv "tools\SadTalker\.venv"
if errorlevel 1 goto failed
"tools\SadTalker\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
"tools\SadTalker\.venv\Scripts\python.exe" -m pip install torch torchvision torchaudio
if errorlevel 1 goto failed
"tools\SadTalker\.venv\Scripts\python.exe" -m pip install -r "tools\SadTalker\requirements.txt"
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0download_models.ps1"
if errorlevel 1 goto failed
echo Engine folder: %~dp0tools\SadTalker
pause
exit /b 0
:failed
echo Installation stopped because a command failed. See the message above.
pause
exit /b 1
