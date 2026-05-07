#!/usr/bin/env python3
"""Concatenate per-scene mp4s with cross-fade transitions via ffmpeg ``xfade``.

The implementer agent calls this after all scenes render. It constructs an
ffmpeg ``-filter_complex`` graph that chains ``xfade`` filters between adjacent
videos and (when audio is present) ``acrossfade`` filters between adjacent audio
streams, then runs ffmpeg in subprocess.

Output contract: a single JSON object on stdout:

    {
      "ok": bool,
      "exit_code": int,
      "total_duration_s": float,
      "command": [<argv>],
      "fallback_used": bool,
      "stderr_tail": "<last 50 lines>"
    }

Exit code 0 on success, 1 on ffmpeg failure (still emits JSON), 2 on argparse /
input errors. ``fallback_used`` is true when xfade is unavailable / fails and
this script falls back to plain concat (no transitions).

CLI::

    python scripts/concat-xfade.py \
      --inputs scene_01.mp4 scene_02.mp4 ... \
      --durations 8.0 6.0 ... \
      --transition-s 0.7 \
      --out out/<run>/video.mp4 \
      [--timeout 120]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_TIMEOUT_S = 120
STDERR_TAIL_LINES = 50


def build_filter_chain(
    n_inputs: int,
    durations: list[float],
    transition_s: float,
    has_audio: bool,
) -> tuple[str, str, str]:
    """Build the filter_complex string + final video/audio map labels.

    Returns ``(filter_complex, video_map, audio_map_or_empty)``.
    """
    if n_inputs < 2:
        # Single input: filter_complex isn't needed; caller handles separately.
        return ("", "[0:v]", "[0:a]" if has_audio else "")

    # Video xfade chain: cumulative sum, offset = sum(d_0..d_i) - T*(i+1)
    video_parts: list[str] = []
    cumulative = 0.0
    prev_v = "[0:v]"
    for i in range(n_inputs - 1):
        cumulative += durations[i]
        offset = cumulative - transition_s * (i + 1)
        # Clamp small negatives caused by transition longer than first scene.
        if offset < 0:
            offset = 0.0
        out_label = f"[v{i + 1}]"
        video_parts.append(
            f"{prev_v}[{i + 1}:v]xfade=transition=fade:"
            f"duration={transition_s}:offset={offset:.4f}{out_label}"
        )
        prev_v = out_label
    final_v = prev_v

    # Audio chain: acrossfade is sequential, no offset. Final duration shrinks
    # by transition_s per join, matching xfade's effect on the video stream.
    audio_parts: list[str] = []
    final_a = ""
    if has_audio:
        prev_a = "[0:a]"
        for i in range(n_inputs - 1):
            out_label = f"[a{i + 1}]"
            audio_parts.append(
                f"{prev_a}[{i + 1}:a]acrossfade=duration={transition_s}{out_label}"
            )
            prev_a = out_label
        final_a = prev_a

    chain = ";".join(video_parts + audio_parts)
    return chain, final_v, final_a


def probe_has_audio(mp4: Path) -> bool:
    """Return True if the mp4 has at least one audio stream."""
    if not shutil.which("ffprobe"):
        return False
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(mp4),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return res.returncode == 0 and "audio" in res.stdout.lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def has_xfade_filter() -> bool:
    """Probe whether the local ffmpeg supports the xfade filter."""
    if not shutil.which("ffmpeg"):
        return False
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=15,
        )
        return res.returncode == 0 and " xfade " in res.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_xfade(
    inputs: list[Path],
    durations: list[float],
    transition_s: float,
    out: Path,
    timeout_s: int,
) -> tuple[bool, int, list[str], str]:
    """Run ffmpeg with the xfade filter chain. Returns (ok, exit_code, cmd, stderr_tail)."""
    has_audio = all(probe_has_audio(p) for p in inputs)
    chain, vmap, amap = build_filter_chain(len(inputs), durations, transition_s, has_audio)
    cmd: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for p in inputs:
        cmd += ["-i", str(p)]
    if chain:
        cmd += ["-filter_complex", chain]
    cmd += ["-map", vmap]
    if amap:
        cmd += ["-map", amap]
    cmd += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
    ]
    if amap:
        cmd += ["-c:a", "aac", "-ar", "44100"]
    cmd += [str(out)]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        tail = "\n".join(res.stderr.splitlines()[-STDERR_TAIL_LINES:])
        return (res.returncode == 0, res.returncode, cmd, tail)
    except subprocess.TimeoutExpired:
        return (False, 124, cmd, f"ffmpeg timed out after {timeout_s}s")
    except FileNotFoundError as exc:
        return (False, 127, cmd, str(exc))


def run_plain_concat(inputs: list[Path], out: Path, timeout_s: int) -> tuple[bool, int, list[str], str]:
    """Plain ffmpeg concat demuxer fallback (no transitions)."""
    list_path = out.parent / f".{out.stem}-concat-list.txt"
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in inputs),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(out),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        tail = "\n".join(res.stderr.splitlines()[-STDERR_TAIL_LINES:])
        return (res.returncode == 0, res.returncode, cmd, tail)
    except subprocess.TimeoutExpired:
        return (False, 124, cmd, f"ffmpeg timed out after {timeout_s}s")
    finally:
        list_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Concatenate scene mp4s with cross-fades.")
    parser.add_argument("--inputs", nargs="+", required=True, type=Path,
                        help="Per-scene mp4 paths in playback order.")
    parser.add_argument("--durations", nargs="+", required=True, type=float,
                        help="Per-scene duration in seconds (one per --inputs).")
    parser.add_argument("--transition-s", type=float, default=0.7)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = parser.parse_args()

    if len(args.inputs) != len(args.durations):
        print("error: --inputs and --durations must have the same length", file=sys.stderr)
        return 2
    for p in args.inputs:
        if not p.exists():
            print(f"error: input not found: {p}", file=sys.stderr)
            return 2
    if not (0.3 <= args.transition_s <= 1.5):
        print(f"error: --transition-s {args.transition_s} out of range [0.3, 1.5]", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Single input shortcut: just copy.
    if len(args.inputs) == 1:
        shutil.copy(args.inputs[0], args.out)
        result = {
            "ok": True, "exit_code": 0,
            "total_duration_s": float(args.durations[0]),
            "command": ["copy", str(args.inputs[0]), str(args.out)],
            "fallback_used": False,
            "stderr_tail": "",
        }
        print(json.dumps(result))
        return 0

    fallback_used = False
    if has_xfade_filter():
        ok, code, cmd, tail = run_xfade(
            args.inputs, args.durations, args.transition_s, args.out, args.timeout,
        )
        if not ok:
            fallback_used = True
            ok, code, cmd, tail = run_plain_concat(args.inputs, args.out, args.timeout)
    else:
        fallback_used = True
        ok, code, cmd, tail = run_plain_concat(args.inputs, args.out, args.timeout)

    total_duration_s = sum(args.durations)
    if not fallback_used:
        # xfade reduces final duration by transition_s per join.
        total_duration_s -= args.transition_s * (len(args.inputs) - 1)

    result = {
        "ok": ok,
        "exit_code": code,
        "total_duration_s": round(total_duration_s, 3),
        "command": cmd,
        "fallback_used": fallback_used,
        "stderr_tail": tail,
    }
    print(json.dumps(result))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
