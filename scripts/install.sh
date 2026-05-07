#!/usr/bin/env bash
# Bootstrap a Python venv for the manim-skill plugin (Linux/macOS).
# Mirrors install.ps1 behavior for POSIX shells.
set -euo pipefail

VENV_PATH="${VENV_PATH:-.venv}"
SKIP_LATEX="${SKIP_LATEX:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) VENV_PATH="$2"; shift 2 ;;
    --skip-latex) SKIP_LATEX=1; shift ;;
    -h|--help)
      sed -n '2,5p' "$0"
      echo
      echo "Usage: $0 [--venv PATH] [--skip-latex]"
      exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
INSTALL_LOG="${TMPDIR:-/tmp}/manim-skill-install.log"

color_step()  { printf '\033[36m==> %s\033[0m\n' "$1"; }
color_warn()  { printf '\033[33m!   %s\033[0m\n' "$1"; }
color_err()   { printf '\033[31mX   %s\033[0m\n' "$1" >&2; }

# --- 1. Ensure uv ---------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  color_step "uv not found. Installing from astral.sh..."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    color_err "Failed to bootstrap uv. Manual install: https://docs.astral.sh/uv/getting-started/installation/"
    exit 2
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
color_step "uv version: $(uv --version)"

# --- 2. Create venv -------------------------------------------------------------
VENV_ABS="$REPO_ROOT/$VENV_PATH"
if [[ -d "$VENV_ABS" ]]; then
  color_step "Reusing existing venv at $VENV_ABS"
else
  color_step "Creating venv at $VENV_ABS (Python 3.11)..."
  uv venv "$VENV_ABS" --python 3.11
fi
VENV_PY="$VENV_ABS/bin/python"

# --- 3. Install dependencies ----------------------------------------------------
color_step "Installing requirements from $REQ_FILE ..."
set +e
uv pip install --python "$VENV_PY" -r "$REQ_FILE" 2>&1 | tee "$INSTALL_LOG"
INSTALL_RC=${PIPESTATUS[0]}
set -e
if [[ $INSTALL_RC -ne 0 ]]; then
  if grep -qiE 'pycairo|cairo\.h' "$INSTALL_LOG"; then
    color_err "pycairo native build failed."
    cat <<'EOF'

Two ways forward:
  Option A. Install Cairo + Pango dev headers, then re-run:
    macOS:  brew install cairo pango pkg-config
    Debian: sudo apt install libcairo2-dev libpango1.0-dev pkg-config

  Option B. Use Conda (skips native compile entirely):
    conda create -n manim python=3.11 -y
    conda activate manim
    conda install -c conda-forge manim -y
    pip install -r scripts/requirements.txt
EOF
    echo "Full install log: $INSTALL_LOG"
    exit 1
  fi
  color_err "Dependency install failed. See log: $INSTALL_LOG"
  exit 1
fi

# --- 4. LaTeX probe (optional) --------------------------------------------------
if [[ "$SKIP_LATEX" != "1" ]]; then
  if command -v xelatex >/dev/null 2>&1; then
    color_step "LaTeX present: $(xelatex --version | head -n1)"
  else
    color_warn "xelatex not found. MathTex/Tex will render empty silently."
    color_warn "Install: macOS 'brew install --cask mactex-no-gui'  |  Debian 'sudo apt install texlive-xetex'"
    color_warn "Re-run with --skip-latex to suppress this warning."
  fi
fi

# --- 5. Import-check report -----------------------------------------------------
color_step "Verifying imports..."
"$VENV_PY" "$SCRIPT_DIR/check-env.py"

echo
color_step "Install complete."
echo "Activate venv with:"
echo "  source $VENV_ABS/bin/activate"
