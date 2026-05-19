"""Silent-MathTex empty-frame detector for render.py.

Manim does NOT raise when xelatex is missing or LaTeX errors are swallowed;
it falls back to an empty VGroup and frames render ~all black around the
expected MathTex region. This module surfaces that as a structured signal.

Strategy:
  - Scan scene source for `MathTex(` / `Tex(`.
  - If present and a video file exists: sample 3 frames via ffmpeg, compute
    near-black pixel ratio per frame, flag if any frame >99% black.
  - Any failure returns nulls — never breaks the render.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

MATHTEX_RE = re.compile(r"\b(?:MathTex|Tex)\s*\(")
# Pixel is "near-black" if R, G, B all under this threshold (0-255).
BLACK_PIXEL_THRESHOLD = 16
# Fraction of near-black pixels above which a frame is suspected of empty-MathTex.
BLACK_FRAME_RATIO_THRESHOLD = 0.99
# Number of frames to sample (start/mid/end).
MATHTEX_FRAME_SAMPLES = 3


def scan_mathtex_usage(scene_file: Path) -> bool:
    """Return True if the scene source mentions `MathTex(` or `Tex(`."""
    try:
        return bool(MATHTEX_RE.search(scene_file.read_text(encoding="utf-8")))
    except OSError:
        return False


def _probe_duration_s(video_path: Path) -> float | None:
    try:
        proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            return None
        return float(proc.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _frame_black_ratio(video_path: Path, timestamp_s: float) -> float | None:
    """Grab one frame at timestamp_s; return fraction of near-black pixels.

    Pipes raw rgb24 through a 160x90 scale filter so per-frame byte volume is
    bounded (43200 bytes) regardless of source resolution.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
            [
                "ffmpeg", "-v", "error", "-ss", f"{timestamp_s:.3f}",
                "-i", str(video_path), "-vframes", "1",
                "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-",
            ],
            capture_output=True, timeout=30,
        )
        if proc.returncode != 0 or len(proc.stdout) < 3:
            return None
    except (OSError, subprocess.SubprocessError):
        return None
    data = proc.stdout
    total = len(data) // 3
    if total == 0:
        return None
    thr = BLACK_PIXEL_THRESHOLD
    near_black = 0
    for i in range(0, total * 3, 3):
        if data[i] < thr and data[i + 1] < thr and data[i + 2] < thr:
            near_black += 1
    return near_black / total


def check_mathtex(scene_file: Path, output_path: str | None, dry_run: bool) -> dict:
    """Return 3-field dict: mathtex_present, mathtex_suspected_empty, black_pixel_ratio.

    Never raises. On any frame-extraction failure, the two derived fields are null.
    """
    present = scan_mathtex_usage(scene_file)
    if dry_run or not output_path:
        return {
            "mathtex_present": present,
            "mathtex_suspected_empty": False if not present else None,
            "black_pixel_ratio": None,
        }
    vp = Path(output_path)
    if not vp.exists():
        return {
            "mathtex_present": present,
            "mathtex_suspected_empty": None,
            "black_pixel_ratio": None,
        }
    duration = _probe_duration_s(vp)
    if not duration or duration <= 0:
        return {
            "mathtex_present": present,
            "mathtex_suspected_empty": None,
            "black_pixel_ratio": None,
        }
    n = MATHTEX_FRAME_SAMPLES
    times = [duration * (i + 1) / (n + 1) for i in range(n)]
    ratios = [_frame_black_ratio(vp, t) for t in times]
    valid = [r for r in ratios if r is not None]
    if not valid:
        return {
            "mathtex_present": present,
            "mathtex_suspected_empty": None,
            "black_pixel_ratio": None,
        }
    max_ratio = max(valid)
    suspected = bool(present and max_ratio > BLACK_FRAME_RATIO_THRESHOLD)
    return {
        "mathtex_present": present,
        "mathtex_suspected_empty": suspected,
        "black_pixel_ratio": round(max_ratio, 4),
    }
