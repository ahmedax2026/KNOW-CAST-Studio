$ErrorActionPreference = 'Stop'
function HasCommand($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function InstallPackage($id) {
  if (!(HasCommand 'winget.exe')) { throw "Missing $id. Install App Installer (winget), or install the dependency manually." }
  Write-Host "Installing $id via winget..."
  & winget.exe install --id $id --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
  if ($LASTEXITCODE -ne 0) { throw "winget failed for $id (exit $LASTEXITCODE)." }
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
if (!(HasCommand 'py.exe')) { InstallPackage 'Python.Python.3.11' }
if (!(HasCommand 'py.exe')) { throw 'Python launcher not visible. Close this window and run the installer again.' }
& py.exe -3.11 -c 'import sys; assert sys.maxsize > 2**32'
if ($LASTEXITCODE -ne 0) { InstallPackage 'Python.Python.3.11' }
if (!(HasCommand 'ffmpeg.exe') -and !(Test-Path "$PSScriptRoot\tools\ffmpeg\bin\ffmpeg.exe")) { InstallPackage 'Gyan.FFmpeg' }
if (!(HasCommand 'ffmpeg.exe') -and !(Test-Path "$PSScriptRoot\tools\ffmpeg\bin\ffmpeg.exe")) {
  throw 'FFmpeg is not visible yet. Restart this installer after winget finishes.'
}
if (!(HasCommand 'git.exe')) { InstallPackage 'Git.Git' }
if (!(HasCommand 'git.exe')) { throw 'Git is not visible yet. Restart this installer.' }
& py.exe -3.8 -c 'import sys; assert sys.maxsize > 2**32' 2>$null
if ($LASTEXITCODE -ne 0) { InstallPackage 'Python.Python.3.8' }
& py.exe -3.8 -c 'import sys; assert sys.maxsize > 2**32'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.8 x64 is not visible yet. Restart this installer.' }
Push-Location $PSScriptRoot
try {
  & cmd.exe /d /c 'call setup_animation_windows.bat <nul'
  if ($LASTEXITCODE -ne 0) { throw 'SadTalker setup failed.' }
  & cmd.exe /d /c 'call install_transcription_windows.bat <nul'
  if ($LASTEXITCODE -ne 0) { throw 'Transcription setup failed.' }
  Write-Host 'Main app and animation engine are ready. Speaker detection remains optional.'
} finally { Pop-Location }
