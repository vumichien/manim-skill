#!/usr/bin/env python3
"""Validate a storyboard YAML against schemas/storyboard.schema.json.

Beyond JSON-Schema syntax, performs cross-checks:
  - every animations[].target resolves to a mobject (by name or index expr)
  - sum of scenes[].duration_s ≈ meta.total_duration_s (±1s tolerance)
  - scene ids form a contiguous scene_01..scene_NN sequence

Exit 0 valid, 1 invalid. Errors print one per line, deepest path first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "storyboard.schema.json"
DURATION_TOLERANCE_S = 1.0
TARGET_INDEX_RE = re.compile(r"^mobjects\[(\d+)\]$")
TARGET_GROUP_RE = re.compile(r"^(?:VGroup|Group|AnimationGroup)\(([^)]+)\)$")
SCENE_ID_RE = re.compile(r"^scene_(\d{2})$")


def _load_yaml(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    return yaml.safe_load(raw)


def _schema_errors(schema: dict, data: dict) -> list[str]:
    errors: list[str] = []
    for err in Draft202012Validator(schema).iter_errors(data):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"schema  {loc}: {err.message}")
    return errors


def _target_names(target: str) -> list[str]:
    """Extract individual mobject names from a target reference."""
    m = TARGET_GROUP_RE.match(target.strip())
    if m:
        return [name.strip() for name in m.group(1).split(",") if name.strip()]
    return [target.strip()]


def _cross_check_targets(data: dict) -> list[str]:
    errors: list[str] = []
    for s_idx, scene in enumerate(data.get("scenes", [])):
        names = {m.get("name") for m in scene.get("mobjects", []) if m.get("name")}
        n_mobjects = len(scene.get("mobjects", []))
        for a_idx, anim in enumerate(scene.get("animations", [])):
            target = anim.get("target", "")
            for t in _target_names(target):
                idx_match = TARGET_INDEX_RE.match(t)
                if idx_match:
                    if int(idx_match.group(1)) >= n_mobjects:
                        errors.append(
                            f"crossref scenes/{s_idx}/animations/{a_idx}/target: "
                            f"index '{t}' out of range (have {n_mobjects} mobjects)"
                        )
                    continue
                if t not in names:
                    errors.append(
                        f"crossref scenes/{s_idx}/animations/{a_idx}/target: "
                        f"'{t}' does not match any mobjects[].name in this scene"
                    )
    return errors


def _cross_check_durations(data: dict) -> list[str]:
    errors: list[str] = []
    declared = float(data.get("meta", {}).get("total_duration_s", 0))
    summed = sum(float(s.get("duration_s", 0)) for s in data.get("scenes", []))
    if abs(declared - summed) > DURATION_TOLERANCE_S:
        errors.append(
            f"crossref meta/total_duration_s: declared {declared}s but scenes sum to "
            f"{summed:.1f}s (tolerance ±{DURATION_TOLERANCE_S}s)"
        )
    return errors


def _cross_check_scene_ids(data: dict) -> list[str]:
    errors: list[str] = []
    expected = 1
    for idx, scene in enumerate(data.get("scenes", [])):
        sid = scene.get("id", "")
        m = SCENE_ID_RE.match(sid)
        if not m:
            errors.append(f"crossref scenes/{idx}/id: '{sid}' does not match scene_NN pattern")
            continue
        if int(m.group(1)) != expected:
            errors.append(
                f"crossref scenes/{idx}/id: expected 'scene_{expected:02d}', got '{sid}'"
            )
        expected += 1
    return errors


def validate(storyboard_path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = _load_yaml(storyboard_path)
    if not isinstance(data, dict):
        return ["root: storyboard must be a YAML mapping"]
    errors = _schema_errors(schema, data)
    # Cross-checks only run if schema-level errors do not prevent traversal.
    if not any(e.startswith("schema  scenes") or e.startswith("schema  meta") for e in errors):
        errors += _cross_check_scene_ids(data)
        errors += _cross_check_targets(data)
        errors += _cross_check_durations(data)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a storyboard.yaml.")
    parser.add_argument("path", type=Path, help="Path to storyboard YAML file.")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help=f"Override schema path (default: {DEFAULT_SCHEMA}).",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2

    errors = validate(args.path, args.schema)
    if errors:
        print(f"INVALID — {len(errors)} error(s) in {args.path}", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(f"OK    {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
