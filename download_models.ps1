$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'tools\SadTalker\checkpoints'
New-Item -ItemType Directory -Force -Path $target | Out-Null
$root = 'https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/'
$names = @(
  'mapping_00109-model.pth.tar',
  'mapping_00229-model.pth.tar',
  'SadTalker_V0.0.2_256.safetensors',
  'SadTalker_V0.0.2_512.safetensors'
)
foreach ($name in $names) {
  $dest = Join-Path $target $name
  if ((Test-Path $dest) -and (Get-Item $dest).Length -gt 1048576) {
    Write-Host "Already present: $name"
    continue
  }
  $partial = "$dest.part"
  Write-Host "Downloading $name ..."
  & curl.exe -fL -C - --retry 3 --retry-delay 3 -o $partial "$root$name"
  if ($LASTEXITCODE -ne 0 -or !(Test-Path $partial) -or (Get-Item $partial).Length -lt 1048576) {
    throw "Download failed or file is too small: $name"
  }
  Move-Item -Force $partial $dest
}
Write-Host 'Core 256/512 models downloaded. Additional face-detection weights may be needed by SadTalker.'
