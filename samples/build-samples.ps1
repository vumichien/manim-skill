<#
.SYNOPSIS
  Render every sample's scene.py + extract a thumbnail PNG.

.DESCRIPTION
  Runs `python -m manim render -qm` against each samples/NN-*/scene.py and
  copies the resulting mp4 to <sample-dir>/out.mp4. Then uses ffmpeg to grab
  a frame near the end of the clip (default: 80% of duration) as
  <sample-dir>/thumb.png. Sampling from the mp4 instead of `--save_last_frame`
  avoids ending up with a black frame for samples that fade out.

  Sample 03 (fourier-math) is skipped if xelatex is missing; it ships a
  pre-rendered placeholder thumb so the README grid still has all six tiles.

.PARAMETER Quality
  Manim quality flag suffix: low | medium | high. Default medium.

.EXAMPLE
  pwsh samples/build-samples.ps1
  pwsh samples/build-samples.ps1 -Quality low
#>
[CmdletBinding()]
param(
    [ValidateSet("low", "medium", "high")]
    [string]$Quality = "medium"
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
$qFlag = @{ low = "-ql"; medium = "-qm"; high = "-qh" }[$Quality]
$qDir  = @{ low = "480p15"; medium = "720p30"; high = "1080p60" }[$Quality]
$hasLatex  = $null -ne (Get-Command xelatex -ErrorAction SilentlyContinue)
$hasFfmpeg = $null -ne (Get-Command ffmpeg  -ErrorAction SilentlyContinue)

$samples = @(
    @{ Dir = "01-pythagoras-2d";    Cls = "Pythagoras2DScene";    NeedsLatex = $false },
    @{ Dir = "02-rotating-cube-3d"; Cls = "RotatingCube3DScene";  NeedsLatex = $false },
    @{ Dir = "03-fourier-math";     Cls = "FourierMathScene";     NeedsLatex = $true  },
    @{ Dir = "04-quadratic-plot";   Cls = "QuadraticPlotScene";   NeedsLatex = $false },
    @{ Dir = "05-text-morph";       Cls = "TextMorphScene";       NeedsLatex = $false },
    @{ Dir = "06-sine-wave-tracker"; Cls = "SineWaveTrackerScene"; NeedsLatex = $false }
)

function Get-VideoDurationSeconds {
    param([string]$Path)
    $probe = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Path 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { return [double]$probe }
    return $null
}

foreach ($s in $samples) {
    $dir = Join-Path $PSScriptRoot $s.Dir
    if ($s.NeedsLatex -and -not $hasLatex) {
        Write-Host "==> Skipping $($s.Dir) (no xelatex on PATH; placeholder thumb retained)" -ForegroundColor Yellow
        continue
    }
    Write-Host "==> Rendering $($s.Dir)..." -ForegroundColor Cyan

    $sceneFile = Join-Path $dir "scene.py"
    $mediaDir  = Join-Path $dir ".manim_media"

    & python -m manim render $qFlag --media_dir $mediaDir $sceneFile $s.Cls
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    render failed for $($s.Dir)" -ForegroundColor Red
        continue
    }
    $mp4 = Join-Path $mediaDir "videos\scene\$qDir\$($s.Cls).mp4"
    $outMp4 = Join-Path $dir "out.mp4"
    if (Test-Path $mp4) {
        Copy-Item $mp4 $outMp4 -Force
    }

    # Thumbnail: prefer ffmpeg-seek-from-mp4 (handles fade-to-black scenes correctly).
    if ($hasFfmpeg -and (Test-Path $outMp4)) {
        $duration = Get-VideoDurationSeconds -Path $outMp4
        $seek = if ($duration) { [math]::Max(0.1, $duration * 0.8) } else { 1.0 }
        $thumb = Join-Path $dir "thumb.png"
        & ffmpeg -y -loglevel error -ss $seek -i $outMp4 -frames:v 1 $thumb 2>$null | Out-Null
    } else {
        # Fallback: manim --save_last_frame (may be empty for fade-out scenes).
        & python -m manim render --save_last_frame $qFlag --media_dir $mediaDir $sceneFile $s.Cls
        $png = Get-ChildItem -Path (Join-Path $mediaDir "images") -Filter "*.png" -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -like "$($s.Cls)*" } |
               Select-Object -First 1
        if ($png) {
            Copy-Item $png.FullName (Join-Path $dir "thumb.png") -Force
        }
    }

    Remove-Item $mediaDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Done." -ForegroundColor Cyan
