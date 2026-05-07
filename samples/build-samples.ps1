<#
.SYNOPSIS
  Render every sample's scene.py + concat with cross-fades + extract thumbnail.

.DESCRIPTION
  Schema 0.2.0 samples ship multiple Scene classes per file (Scene01, Scene02, ...).
  This script:
    1. Renders each Scene class via `python -m manim render -q<flag>`.
    2. Concatenates per-scene mp4s into <sample-dir>/out.mp4 via scripts/concat-xfade.py
       (xfade transitions). Single-scene samples copy the mp4 directly.
    3. Extracts a thumbnail (frame at 80% of duration via ffmpeg seek).

  Sample 03 (fourier-math) is LaTeX-free since 0.2.0 and renders unconditionally.

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
$hasFfmpeg = $null -ne (Get-Command ffmpeg  -ErrorAction SilentlyContinue)

# Each sample lists per-scene class names + their storyboard durations (seconds).
$samples = @(
    @{ Dir = "01-pythagoras-2d";     Classes = @("Scene01","Scene02","Scene03"); Durations = @(7.0, 7.0, 4.0) },
    @{ Dir = "02-rotating-cube-3d";  Classes = @("Scene01");                     Durations = @(9.0)            },
    @{ Dir = "03-fourier-math";      Classes = @("Scene01","Scene02");           Durations = @(6.0, 6.0)       },
    @{ Dir = "04-quadratic-plot";    Classes = @("Scene01");                     Durations = @(9.0)            },
    @{ Dir = "05-text-morph";        Classes = @("Scene01");                     Durations = @(6.0)            },
    @{ Dir = "06-sine-wave-tracker"; Classes = @("Scene01","Scene02");           Durations = @(3.0, 5.0)       }
)

function Get-VideoDurationSeconds {
    param([string]$Path)
    $probe = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Path 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { return [double]$probe }
    return $null
}

foreach ($s in $samples) {
    $dir = Join-Path $PSScriptRoot $s.Dir
    Write-Host "==> Rendering $($s.Dir) ($($s.Classes.Count) scene(s))..." -ForegroundColor Cyan

    $sceneFile = Join-Path $dir "scene.py"
    $mediaDir  = Join-Path $dir ".manim_media"
    $sceneMp4s = @()
    $rendered = $true

    foreach ($cls in $s.Classes) {
        & python -m manim render $qFlag --media_dir $mediaDir $sceneFile $cls
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    render failed for $($s.Dir)/$cls" -ForegroundColor Red
            $rendered = $false
            break
        }
        $mp4 = Join-Path $mediaDir "videos\scene\$qDir\$cls.mp4"
        if (Test-Path $mp4) { $sceneMp4s += $mp4 }
    }

    if (-not $rendered -or $sceneMp4s.Count -eq 0) {
        Remove-Item $mediaDir -Recurse -Force -ErrorAction SilentlyContinue
        continue
    }

    $outMp4 = Join-Path $dir "out.mp4"
    if ($sceneMp4s.Count -eq 1) {
        Copy-Item $sceneMp4s[0] $outMp4 -Force
    } else {
        $concatScript = Join-Path $repoRoot "scripts\concat-xfade.py"
        $concatArgs = @("--inputs") + $sceneMp4s + @("--durations") + $s.Durations + @("--transition-s","0.7","--out",$outMp4)
        $concatJson = & python $concatScript @concatArgs 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    concat-xfade failed for $($s.Dir): $concatJson" -ForegroundColor Yellow
        }
    }

    # Thumbnail: ffmpeg-seek-from-mp4 (handles fade-to-black scenes correctly).
    if ($hasFfmpeg -and (Test-Path $outMp4)) {
        $duration = Get-VideoDurationSeconds -Path $outMp4
        $seek = if ($duration) { [math]::Max(0.1, $duration * 0.8) } else { 1.0 }
        $thumb = Join-Path $dir "thumb.png"
        & ffmpeg -y -loglevel error -ss $seek -i $outMp4 -frames:v 1 $thumb 2>$null | Out-Null
    }

    Remove-Item $mediaDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "==> Done." -ForegroundColor Cyan
