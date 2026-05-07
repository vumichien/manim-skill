<#
.SYNOPSIS
  Bootstrap a Python venv for the manim-skill plugin (Windows-first).

.DESCRIPTION
  Creates .venv/ via uv, installs Manim + voiceover + ingest deps,
  probes LaTeX, and exits with actionable errors on pycairo native
  build failure (the one remaining Windows pain point in 2026-Q2).

.PARAMETER VenvPath
  Path to create the venv. Defaults to ".venv" relative to CWD.

.PARAMETER SkipLatex
  Skip the optional xelatex probe.

.EXAMPLE
  pwsh scripts\install.ps1
  pwsh scripts\install.ps1 -VenvPath C:\envs\manim
#>
[CmdletBinding()]
param(
    [string]$VenvPath = ".venv",
    [switch]$SkipLatex
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$reqFile  = Join-Path $PSScriptRoot "requirements.txt"

function Write-Step  { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Warn2 { param($m) Write-Host "!   $m" -ForegroundColor Yellow }
function Write-Err2  { param($m) Write-Host "X   $m" -ForegroundColor Red }

# --- 1. Ensure uv is available --------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Step "uv not found. Installing from astral.sh..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    } catch {
        Write-Err2 "Failed to bootstrap uv. Manual install: https://docs.astral.sh/uv/getting-started/installation/"
        exit 2
    }
    # Refresh PATH so the freshly installed uv is visible in this session.
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
}
Write-Step ("uv version: " + (& uv --version))

# --- 2. Create venv -------------------------------------------------------------
$venvAbs = Join-Path $repoRoot $VenvPath
if (Test-Path $venvAbs) {
    Write-Step "Reusing existing venv at $venvAbs"
} else {
    Write-Step "Creating venv at $venvAbs (Python 3.11)..."
    & uv venv $venvAbs --python 3.11
    if ($LASTEXITCODE -ne 0) {
        Write-Err2 "uv venv failed. Ensure Python 3.11+ is installed (uv can manage Python: 'uv python install 3.11')."
        exit 2
    }
}
$venvPython = Join-Path $venvAbs "Scripts\python.exe"

# --- 3. Install dependencies ----------------------------------------------------
Write-Step "Installing requirements from $reqFile ..."
$installLog = Join-Path $env:TEMP "manim-skill-install.log"
& uv pip install --python $venvPython -r $reqFile 2>&1 | Tee-Object -FilePath $installLog
if ($LASTEXITCODE -ne 0) {
    $logTail = Get-Content $installLog -Tail 60 -ErrorAction SilentlyContinue
    if ($logTail -match "(?i)pycairo|cairo\.h|Microsoft Visual C\+\+") {
        Write-Err2 "pycairo native build failed (the only Windows snag in 2026-Q2)."
        Write-Host ""
        Write-Host "Two ways forward:"
        Write-Host "  Option A. Install MSVC Build Tools, then re-run this script:"
        Write-Host "    https://visualstudio.microsoft.com/downloads/"
        Write-Host "    Workload: 'Desktop development with C++'"
        Write-Host ""
        Write-Host "  Option B. Use Conda (skips native compile entirely):"
        Write-Host "    conda create -n manim python=3.11 -y"
        Write-Host "    conda activate manim"
        Write-Host "    conda install -c conda-forge manim -y"
        Write-Host "    pip install -r scripts/requirements.txt"
        Write-Host ""
        Write-Host "Full install log: $installLog"
        exit 1
    }
    Write-Err2 "Dependency install failed. See log: $installLog"
    exit 1
}

# --- 4. LaTeX probe (optional) --------------------------------------------------
if (-not $SkipLatex) {
    if (Get-Command xelatex -ErrorAction SilentlyContinue) {
        $xv = (& xelatex --version | Select-Object -First 1)
        Write-Step "LaTeX present: $xv"
    } else {
        Write-Warn2 "xelatex not found. MathTex/Tex will render empty silently."
        Write-Warn2 "Install MiKTeX (recommended): https://miktex.org/download"
        Write-Warn2 "Re-run with -SkipLatex to suppress this warning."
    }
}

# --- 5. Import-check report -----------------------------------------------------
Write-Step "Verifying imports..."
& $venvPython (Join-Path $PSScriptRoot "check-env.py")
if ($LASTEXITCODE -ne 0) {
    Write-Err2 "check-env.py reported missing modules. Re-run install or inspect log: $installLog"
    exit 1
}

Write-Host ""
Write-Step "Install complete."
Write-Host "Activate venv with:"
Write-Host "  & '$venvAbs\Scripts\Activate.ps1'"
exit 0
