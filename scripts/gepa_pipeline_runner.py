"""Orchestrator for one GEPA pipeline run.

`run(candidate, topic) -> PipelineTrace`:
  1. Prepare per-candidate working dir under plans/gepa-runs/<run-id>/candidates/<n>/.
  2. Invoke configured transport (default: LitellmTransport) to produce
     storyboard.yaml + scene_NN.py files.
  3. Validate storyboard against schemas/storyboard.schema.json.
  4. Render each scene via scripts/render.py (low quality by default).
  5. Assemble PipelineTrace consumed by gepa_metrics.composite_score.

`run_valset(candidate, valset)` re-renders the canonical samples/01-06
against the candidate's implementer prompt and returns per-sample pass/fail.
This is the regression guard input.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gepa_invoke_agents import LitellmTransport, Transport, TransportResult  # noqa: E402
from gepa_metrics import PipelineTrace, RenderResult  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDER_PY = REPO_ROOT / "scripts" / "render.py"
VALIDATE_PY = REPO_ROOT / "scripts" / "validate-storyboard.py"
RUNS_ROOT = REPO_ROOT / "plans" / "gepa-runs"


def _validate_storyboard(yaml_path: Path) -> tuple[bool, list[str]]:
    """Shell out to scripts/validate-storyboard.py; return (ok, errors)."""
    if not yaml_path or not yaml_path.exists():
        return False, ["storyboard.yaml missing"]
    try:
        proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
            [sys.executable, str(VALIDATE_PY), str(yaml_path)],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, [f"validator subprocess failed: {exc!s}"]
    if proc.returncode == 0:
        return True, []
    errors = [
        line.strip()
        for line in (proc.stderr or "").splitlines()
        if line.strip() and not line.startswith("INVALID")
    ]
    return False, errors[:50]


def _scene_class_name(scene_file: Path) -> str:
    """Pull the first `class XYZ(Scene` from the file; default 'Scene01'."""
    try:
        text = scene_file.read_text(encoding="utf-8")
    except OSError:
        return "Scene01"
    import re
    m = re.search(r"class\s+(\w+)\s*\([^)]*Scene", text)
    return m.group(1) if m else "Scene01"


def _render_scene(scene_file: Path, work_dir: Path, quality: str, dry_run: bool) -> dict:
    """Run scripts/render.py and parse the JSON contract."""
    cmd = [
        sys.executable, str(RENDER_PY),
        "--scene-file", str(scene_file),
        "--class-name", _scene_class_name(scene_file),
        "--quality", quality,
        "--out-dir", str(work_dir / "render"),
    ]
    if dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)  # noqa: S603
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error_class": "timeout", "stderr_tail": str(exc)}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error_class": "other", "stderr_tail": (proc.stderr or "")[-500:]}


def _scenes_from_storyboard(yaml_path: Path) -> int:
    """Count scenes declared in storyboard for `scenes_total`."""
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return 0
    if not isinstance(data, dict):
        # Empty/invalid YAML → safe_load returns None or a scalar.
        return 0
    scenes = data.get("scenes")
    return len(scenes) if isinstance(scenes, list) else 0


def _prepare_candidate_dir(run_id: str, idx: int) -> Path:
    out = RUNS_ROOT / run_id / "candidates" / f"{idx:03d}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _collect_render_results(scenes: tuple[Path, ...], work_dir: Path, quality: str, dry_run: bool) -> list[RenderResult]:
    results: list[RenderResult] = []
    for s in scenes:
        payload = _render_scene(s, work_dir, quality, dry_run)
        results.append(
            RenderResult(
                scene_id=s.stem,
                ok=bool(payload.get("ok")),
                error_class=payload.get("error_class"),
                stderr_tail=(payload.get("stderr_tail") or "")[:500],
                mathtex_present=bool(payload.get("mathtex_present", False)),
                mathtex_suspected_empty=payload.get("mathtex_suspected_empty"),
            )
        )
    return results


def run(
    candidate: dict[str, str],
    topic: str,
    *,
    transport: Transport | None = None,
    quality: str = "low",
    dry_run: bool = False,
    run_id: str = "adhoc",
    candidate_idx: int = 0,
    regression: dict[str, bool] | None = None,
) -> PipelineTrace:
    """Execute one pipeline run; return a PipelineTrace."""
    transport = transport or LitellmTransport()
    work_dir = _prepare_candidate_dir(run_id, candidate_idx)

    tr: TransportResult = transport.run(candidate, topic, work_dir)
    if tr.storyboard_path is None:
        return PipelineTrace(
            topic=topic,
            storyboard_valid=False,
            schema_errors=(tr.transport_error or "transport produced no storyboard",),
            scenes_total=0,
            scenes_rendered=0,
            render_results=(),
            regression=regression or {},
        )

    valid, errors = _validate_storyboard(tr.storyboard_path)
    scenes_total = _scenes_from_storyboard(tr.storyboard_path)
    render_results = _collect_render_results(tr.scene_files, work_dir, quality, dry_run) if valid else []
    scenes_rendered = sum(1 for r in render_results if r.ok)

    return PipelineTrace(
        topic=topic,
        storyboard_valid=valid,
        schema_errors=tuple(errors),
        scenes_total=scenes_total,
        scenes_rendered=scenes_rendered,
        render_results=tuple(render_results),
        regression=regression or {},
    )


def run_valset(candidate: dict[str, str], valset: list[dict], *, quality: str = "low", dry_run: bool = False) -> dict[str, bool]:
    """Re-render canonical sample storyboards; return {sample_id: pass}.

    The valset reuses the already-validated storyboards in samples/01-06 — we
    don't re-invoke the researcher/planner here. `candidate` is currently a
    no-op for the rendered scene files (they're checked-in `scene.py`); the
    valset path therefore only verifies the implementer-rendered output for
    regression. A future Path A run will swap in scenes generated from the
    candidate-implementer prompt.
    """
    out: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="gepa-val-") as tmp:
        work_dir = Path(tmp)
        for entry in valset:
            sample_id = entry["id"]
            sb_path = REPO_ROOT / entry["storyboard_path"]
            scene_path = REPO_ROOT / entry["scene_path"]
            sb_ok, _ = _validate_storyboard(sb_path)
            if not sb_ok:
                out[sample_id] = False
                continue
            payload = _render_scene(scene_path, work_dir / sample_id, quality, dry_run)
            out[sample_id] = bool(payload.get("ok")) and not payload.get("mathtex_suspected_empty")
    return out
