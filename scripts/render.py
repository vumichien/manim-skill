#!/usr/bin/env python3
"""Headless wrapper around `python -m manim render`.

Returns a single JSON object on stdout describing the render outcome,
so the implementer agent can act on structured signals instead of
parsing Manim tracebacks.

Usage:
  python scripts/render.py --scene-file PATH --class-name CLS [opts]

JSON contract (stable):
  {
    "ok": bool,
    "exit_code": int,
    "render_time_s": float,
    "output_path": str | null,
    "error_class": "latex" | "import" | "name" | "type" | "timeout" | "other" | null,
    "stderr_tail": str,
    "command": [str]
  }
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

QUALITY_FLAG: dict[str, str] = {"low": "-ql", "medium": "-qm", "high": "-qh", "4k": "-qk"}
QUALITY_DIR: dict[str, str] = {
    "low": "480p15",
    "medium": "720p30",
    "high": "1080p60",
    "4k": "2160p60",
}
ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("latex", re.compile(r"latex.*(returned non-zero|failed|error)|xelatex|miktex", re.I)),
    ("import", re.compile(r"ModuleNotFoundError|ImportError")),
    ("name", re.compile(r"NameError: name [\"']\w+[\"'] is not defined")),
    ("type", re.compile(r"TypeError")),
]
DEFAULT_TIMEOUT_S = 600
STDERR_TAIL_LINES = 50


def classify(stderr: str) -> str:
    for name, pat in ERROR_PATTERNS:
        if pat.search(stderr):
            return name
    return "other"


def find_output(scene_file: Path, class_name: str, quality: str, gif: bool, media_dir: Path) -> str | None:
    """Glob for the rendered file. Manim writes to:
    <media_dir>/videos/<scene_stem>/<quality_dir>/<ClassName>.{mp4,gif}
    """
    ext = "gif" if gif else "mp4"
    quality_subdir = QUALITY_DIR[quality]
    candidate = media_dir / "videos" / scene_file.stem / quality_subdir / f"{class_name}.{ext}"
    if candidate.exists():
        return candidate.as_posix()
    # Fallback glob in case Manim renames or quality subdir differs.
    for hit in (media_dir / "videos").rglob(f"{class_name}.{ext}"):
        return hit.as_posix()
    return None


def build_command(args: argparse.Namespace, media_dir: Path) -> list[str]:
    cmd = [
        sys.executable, "-m", "manim", "render",
        QUALITY_FLAG[args.quality],
        "--media_dir", str(media_dir),
    ]
    if args.dry_run:
        cmd.append("--dry_run")
    if args.gif:
        cmd += ["--format", "gif"]
    cmd += [str(args.scene_file), args.class_name]
    return cmd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scene-file", type=Path, required=True)
    p.add_argument("--class-name", required=True)
    p.add_argument("--quality", choices=list(QUALITY_FLAG), default="high")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--gif", action="store_true")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args()

    if not args.scene_file.exists():
        print(json.dumps({
            "ok": False, "exit_code": 2, "error_class": "other",
            "stderr_tail": f"scene file not found: {args.scene_file}",
            "command": [], "render_time_s": 0.0, "output_path": None,
        }))
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    media_dir = args.out_dir / "manim_media"
    cmd = build_command(args, media_dir)

    t0 = time.time()
    try:
        proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
            cmd, capture_output=True, text=True, timeout=args.timeout
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - t0
        print(json.dumps({
            "ok": False, "exit_code": -1, "render_time_s": round(elapsed, 1),
            "output_path": None, "error_class": "timeout",
            "stderr_tail": f"Timeout after {args.timeout}s. Last stderr: {(exc.stderr or '')[-1000:]}",
            "command": cmd,
        }, indent=2))
        return 1

    elapsed = time.time() - t0
    ok = proc.returncode == 0
    output_path = (
        find_output(args.scene_file, args.class_name, args.quality, args.gif, media_dir)
        if ok and not args.dry_run
        else None
    )
    stderr_tail = "\n".join(proc.stderr.splitlines()[-STDERR_TAIL_LINES:]) if not ok else ""

    result = {
        "ok": ok,
        "exit_code": proc.returncode,
        "render_time_s": round(elapsed, 1),
        "output_path": output_path,
        "error_class": None if ok else classify(proc.stderr),
        "stderr_tail": stderr_tail,
        "command": cmd,
    }
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
