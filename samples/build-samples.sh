#!/usr/bin/env bash
# Render every sample's scene.py + extract a thumbnail PNG.
# Sample 03 (fourier-math) is skipped if xelatex is missing.
set -uo pipefail

QUALITY="${1:-medium}"
case "$QUALITY" in
  low)    QFLAG="-ql"; QDIR="480p15"  ;;
  medium) QFLAG="-qm"; QDIR="720p30"  ;;
  high)   QFLAG="-qh"; QDIR="1080p60" ;;
  *) echo "Quality must be low|medium|high"; exit 2 ;;
esac

if command -v xelatex >/dev/null 2>&1; then HAS_LATEX=1; else HAS_LATEX=0; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

samples=(
  "01-pythagoras-2d:Pythagoras2DScene:0"
  "02-rotating-cube-3d:RotatingCube3DScene:0"
  "03-fourier-math:FourierMathScene:1"
  "04-quadratic-plot:QuadraticPlotScene:0"
  "05-text-morph:TextMorphScene:0"
)

for entry in "${samples[@]}"; do
  IFS=':' read -r dir cls needs_latex <<<"$entry"
  if [[ "$needs_latex" == "1" && "$HAS_LATEX" == "0" ]]; then
    echo "==> Skipping $dir (no xelatex on PATH)"
    continue
  fi
  echo "==> Rendering $dir..."

  sample_dir="$SCRIPT_DIR/$dir"
  scene_file="$sample_dir/scene.py"
  media_dir="$sample_dir/.manim_media"

  python -m manim render $QFLAG --media_dir "$media_dir" "$scene_file" "$cls" || {
    echo "    render failed for $dir"
    continue
  }
  mp4_path="$media_dir/videos/scene/$QDIR/$cls.mp4"
  [[ -f "$mp4_path" ]] && cp "$mp4_path" "$sample_dir/out.mp4"

  python -m manim render --save_last_frame $QFLAG --media_dir "$media_dir" "$scene_file" "$cls" >/dev/null 2>&1
  png_path=$(find "$media_dir/images" -name "${cls}*.png" -type f 2>/dev/null | head -n1)
  [[ -n "${png_path:-}" ]] && cp "$png_path" "$sample_dir/thumb.png"

  rm -rf "$media_dir"
done

echo "==> Done."
