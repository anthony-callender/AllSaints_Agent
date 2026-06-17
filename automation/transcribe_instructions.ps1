$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$localBin = Join-Path $root ".bin"
if (Test-Path $localBin) {
  $env:PATH = "$localBin;$env:PATH"
}
$videos = @(
  "AllSaintsSermons-1.mp4",
  "AllSaintsSermons-2.mp4",
  "AllSaintsSermons-3.mp4",
  "AllSaintsSermons-4.mp4"
)

if (-not (Get-Command whisper -ErrorAction SilentlyContinue)) {
  throw "whisper is not installed or not on PATH."
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  throw "ffmpeg is not installed or not on PATH. Run: python .\automation\setup_ffmpeg.py"
}

foreach ($video in $videos) {
  $path = Join-Path $root $video
  if (-not (Test-Path $path)) {
    Write-Warning "Missing $video"
    continue
  }

  Write-Host "Transcribing $video"
  whisper $path --model base --language English --output_dir $root
}
