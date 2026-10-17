[CmdletBinding()]
param([switch]$Folder)
$ErrorActionPreference = 'Stop'
$buildArgs = @('run', '--locked', '--group', 'build', '--project', $PSScriptRoot,
    'python', (Join-Path $PSScriptRoot 'build_desktop.py'))
if ($Folder) { $buildArgs += '--onedir' }
& uv @buildArgs
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
