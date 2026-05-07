#!/usr/bin/env python3
"""Emit a captions.srt file for a rendered run.

Reads a storyboard YAML (schema 0.2.0) and the render.log JSON-Lines, then writes
a single SRT file at --out. Per-scene voiceover_text is chunked (10 words/chunk by
default) and distributed across the scene's actual rendered duration (preferring
render.log's render_time_s when available, falling back to storyboard.duration_s).

Cumulative offsets are computed scene-by-scene so the SRT lines up with the
concatenated video. Cross-fade overlap (meta.transition_s) is treated as zero in
SRT output by design — captions stay in their scene's slot rather than overlap.

Exit 0 on success, 1 on parse/IO error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

DEFAULT_WORDS_PER_CHUNK = 10


def chunk_words(text: str, total_s: float, words_per_chunk: int) -> list[tuple[str, float, float]]:
    """Split text into chunks distributed proportionally across total_s."""
    words = (text or "").split()
    if not words or total_s <= 0:
        return []
    groups: list[list[str]] = []
    for i in range(0, len(words), max(words_per_chunk, 1)):
        groups.append(words[i : i + words_per_chunk])
    total_words = sum(len(g) for g in groups)
    out: list[tuple[str, float, float]] = []
    cursor = 0.0
    for g in groups:
        share = (len(g) / total_words) * total_s
        out.append((" ".join(g), cursor, cursor + share))
        cursor += share
    last_text, last_start, _ = out[-1]
    out[-1] = (last_text, last_start, total_s)
    return out


def fmt_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600 * 1000)
    m, ms = divmod(ms, 60 * 1000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_durations(render_log: Path) -> dict[str, float]:
    """Extract observed render durations per scene_id from render.log JSON-Lines."""
    out: dict[str, float] = {}
    if not render_log.exists():
        return out
    for raw in render_log.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if obj.get("stage") == "render" and obj.get("ok") and "scene_id" in obj:
            sid = obj["scene_id"]
            # Prefer the most recent successful render's duration.
            if "scene_duration_s" in obj:
                out[sid] = float(obj["scene_duration_s"])
            elif "render_time_s" in obj:
                # render_time_s is wall clock, not scene length — use only as fallback hint.
                out.setdefault(sid, float(obj["render_time_s"]))
    return out


def build_srt(storyboard: dict, observed: dict[str, float], words_per_chunk: int) -> str:
    """Walk scenes in order, emit SRT entries with cumulative offsets."""
    lines: list[str] = []
    counter = 1
    cursor = 0.0
    for scene in storyboard.get("scenes", []):
        sid = scene.get("id", "")
        duration_s = float(scene.get("duration_s", 0))
        # Use observed scene duration when present and roughly matches storyboard.
        observed_s = observed.get(sid)
        if observed_s and abs(observed_s - duration_s) < max(duration_s * 0.5, 5.0):
            duration_s = observed_s
        text = scene.get("voiceover_text") or ""
        chunks = chunk_words(text, duration_s, words_per_chunk)
        for chunk_text, start_s, end_s in chunks:
            lines.append(str(counter))
            lines.append(f"{fmt_srt_time(cursor + start_s)} --> {fmt_srt_time(cursor + end_s)}")
            lines.append(chunk_text)
            lines.append("")
            counter += 1
        cursor += duration_s
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit captions.srt from storyboard + render.log")
    parser.add_argument("--storyboard", type=Path, required=True)
    parser.add_argument("--render-log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--words-per-chunk", type=int, default=DEFAULT_WORDS_PER_CHUNK)
    args = parser.parse_args()

    if not args.storyboard.exists():
        print(f"error: storyboard not found: {args.storyboard}", file=sys.stderr)
        return 1
    storyboard = yaml.safe_load(args.storyboard.read_text(encoding="utf-8"))
    if not isinstance(storyboard, dict):
        print(f"error: storyboard is not a YAML mapping: {args.storyboard}", file=sys.stderr)
        return 1

    observed = render_durations(args.render_log)
    srt = build_srt(storyboard, observed, args.words_per_chunk)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(srt, encoding="utf-8")
    print(f"OK    {args.out}  ({srt.count(chr(10) + chr(10))} captions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
