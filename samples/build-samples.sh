#!/usr/bin/env bash
# Render every sample's scene.py + concat with cross-fades + extract thumbnail.
#
# Schema 0.2.0 samples ship multiple Scene classes per file (Scene01, Scene02, ...).
# This script renders each class, then concatenates per-scene mp4s into out.mp4
# via scripts/concat-xfade.py with cross-fade transitions. Single-scene samples
# copy the mp4 directly. Thumbnails are sampled from out.mp4 at ~80% duration.
set -uo pipefail

QUALITY="${1:-medium}"
case "$QUALITY" in
  low)    QFLAG="-ql"; QDIR="480p15"  ;;
  medium) QFLAG="-qm"; QDIR="720p30"  ;;
  high)   QFLAG="-qh"; QDIR="1080p60" ;;
  *) echo "Quality must be low|medium|high"; exit 2 ;;
esac

if command -v ffmpeg >/dev/null 2>&1; then HAS_FFMPEG=1; else HAS_FFMPEG=0; fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# entry format: dir:class1,class2,...:dur1,dur2,...
samples=(
  "01-pythagoras-2d:Scene01,Scene02,Scene03:7.0,7.0,4.0"
  "02-rotating-cube-3d:Scene01:9.0"
  "03-fourier-math:Scene01,Scene02:6.0,6.0"
  "04-quadratic-plot:Scene01:9.0"
  "05-text-morph:Scene01:6.0"
  "06-sine-wave-tracker:Scene01,Scene02:3.0,5.0"
)

video_duration_seconds() {
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null
}

for entry in "${samples[@]}"; do
  IFS=':' read -r dir classes durations <<<"$entry"
  echo "==> Rendering $dir..."

  sample_dir="$SCRIPT_DIR/$dir"
  scene_file="$sample_dir/scene.py"
  media_dir="$sample_dir/.manim_media"
  mp4_paths=()
  rendered=1

  IFS=',' read -ra cls_arr <<<"$classes"
  IFS=',' read -ra dur_arr <<<"$durations"

  for cls in "${cls_arr[@]}"; do
    python -m manim render $QFLAG --media_dir "$media_dir" "$scene_file" "$cls" || {
      echo "    render failed for $dir/$cls"
      rendered=0
      break
    }
    mp4_path="$media_dir/videos/scene/$QDIR/$cls.mp4"
    [[ -f "$mp4_path" ]] && mp4_paths+=("$mp4_path")
  done

  if [[ "$rendered" == "0" || ${#mp4_paths[@]} -eq 0 ]]; then
    rm -rf "$media_dir"
    continue
  fi

  out_mp4="$sample_dir/out.mp4"
  if [[ ${#mp4_paths[@]} -eq 1 ]]; then
    cp "${mp4_paths[0]}" "$out_mp4"
  else
    python "$REPO_ROOT/scripts/concat-xfade.py" \
      --inputs "${mp4_paths[@]}" \
      --durations "${dur_arr[@]}" \
      --transition-s 0.7 \
      --out "$out_mp4" >/dev/null || echo "    concat-xfade failed for $dir"
  fi

  if [[ "$HAS_FFMPEG" == "1" && -f "$out_mp4" ]]; then
    duration=$(video_duration_seconds "$out_mp4")
    if [[ -n "$duration" ]]; then
      seek=$(awk -v d="$duration" 'BEGIN { v = d * 0.8; if (v < 0.1) v = 0.1; print v }')
    else
      seek="1.0"
    fi
    ffmpeg -y -loglevel error -ss "$seek" -i "$out_mp4" -frames:v 1 "$sample_dir/thumb.png" >/dev/null 2>&1
  fi

  rm -rf "$media_dir"
done

echo "==> Done."
