<#
.SYNOPSIS
  Render every sample's scene.py + extract a thumbnail PNG.

.DESCRIPTION
  Runs `python -m manim render -qm` against each samples/NN-*/scene.py and
  copies the resulting mp4 to <sample-dir>/out.mp4. Then runs
  `--save_last_frame` to produce <sample-dir>/thumb.png.

  Sample 03 (fourier-math) is skipped if xelatex is missing.

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
$hasLatex = $null -ne (Get-Command xelatex -ErrorAction SilentlyContinue)

$samples = @(
    @{ Dir = "01-pythagoras-2d";   Cls = "Pythagoras2DScene";   NeedsLatex = $false },
    @{ Dir = "02-rotating-cube-3d"; Cls = "RotatingCube3DScene"; NeedsLatex = $false },
    @{ Dir = "03-fourier-math";    Cls = "FourierMathScene";    NeedsLatex = $true },
    @{ Dir = "04-quadratic-plot";  Cls = "QuadraticPlotScene";  NeedsLatex = $false },
    @{ Dir = "05-text-morph";      Cls = "TextMorphScene";      NeedsLatex = $false }
)

foreach ($s in $samples) {
    $dir = Join-Path $PSScriptRoot $s.Dir
    if ($s.NeedsLatex -and -not $hasLatex) {
        Write-Host "==> Skipping $($s.Dir) (no xelatex on PATH)" -ForegroundColor Yellow
        continue
    }
    Write-Host "==> Rendering $($s.Dir)..." -ForegroundColor Cyan

    $sceneFile = Join-Path $dir "scene.py"
    $mediaDir  = Join-Path $dir ".manim_media"

    # Render mp4
    & python -m manim render $qFlag --media_dir $mediaDir $sceneFile $s.Cls
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    render failed for $($s.Dir)" -ForegroundColor Red
        continue
    }
    $mp4 = Join-Path $mediaDir "videos\scene\$qDir\$($s.Cls).mp4"
    if (Test-Path $mp4) {
        Copy-Item $mp4 (Join-Path $dir "out.mp4") -Force
    }

    # Extract last-frame thumbnail
    & python -m manim render --save_last_frame $qFlag --media_dir $mediaDir $sceneFile $s.Cls
    $png = Get-ChildItem -Path (Join-Path $mediaDir "images") -Filter "*.png" -Recurse -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like "$($s.Cls)*" } |
           Select-Object -First 1
    if ($png) {
        Copy-Item $png.FullName (Join-Path $dir "thumb.png") -Force
    }

    # Clean up scratch dir to keep repo tidy
    Remove-Item $mediaDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Done." -ForegroundColor Cyan
