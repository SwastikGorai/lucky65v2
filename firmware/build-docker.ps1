[CmdletBinding()]
param([switch]$Stock, [switch]$Clean)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI is missing. Install Docker Desktop with the Linux engine.'
}
try { $engine = & docker info --format '{{.OSType}}' 2>$null }
catch { $engine = $null }
if ($LASTEXITCODE -ne 0 -or $engine -ne 'linux') {
    throw 'Docker Linux engine is unavailable. Start Docker Desktop in Linux containers mode, then retry.'
}
$repo = Split-Path $PSScriptRoot -Parent
$output = Join-Path $repo 'build/firmware'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$image = 'lucky65-firmware:local'
# Keep the image ID stable on cached builds; provenance timestamps change it.
& docker build --provenance=false --platform linux/amd64 -t $image -f (Join-Path $PSScriptRoot 'Dockerfile') $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw "Build image failed (exit $LASTEXITCODE)." }
$imageId = & docker image inspect --format '{{.Id}}' $image
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the build image.' }
$script = if ($Stock) { '/src/firmware/build-stock.sh' } else { '/src/firmware/build.sh' }
$runArgs = @('run', '--rm', '--platform', 'linux/amd64',
    '--mount', "type=bind,source=$repo,target=/src,readonly",
    '--mount', 'type=volume,source=lucky65-firmware-cache,target=/cache',
    '--mount', "type=bind,source=$output,target=/out",
    '--env', "BUILD_IMAGE_ID=$imageId", $imageId, 'bash', $script)
if ($Clean) { $runArgs += '--clean' }
& docker @runArgs
if ($LASTEXITCODE -ne 0) { throw "Firmware build failed (exit $LASTEXITCODE)." }
