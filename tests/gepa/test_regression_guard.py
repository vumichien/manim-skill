"""Phase 08 — sample-regression guard.

Re-renders the 6 canonical samples using the CURRENT `agents/manim-*.md` files
and asserts each one:
  - has a valid storyboard,
  - renders without error (at --quality low),
  - is not silently empty due to missing MathTex.

Skipped unless `manim` is importable; the GitHub workflow installs it before
running this. Also opt-in via env var GEPA_REGRESSION_GUARD=1 so local
`pytest tests/` is not blocked by sample renders (each sample takes seconds).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
VALSET_YAML = REPO / "tests" / "gepa" / "valset.yaml"


pytestmark = pytest.mark.skipif(
    not os.environ.get("GEPA_REGRESSION_GUARD"),
    reason="Set GEPA_REGRESSION_GUARD=1 to enable; CI workflow sets it",
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def _read_current_candidate() -> dict[str, str]:
    """Read the LIVE agent prompts that a PR is proposing."""
    out = {}
    for key in ("researcher", "planner", "implementer"):
        p = REPO / "agents" / f"manim-{key}.md"
        out[key] = p.read_text(encoding="utf-8")
    return out


def test_manim_is_installed() -> None:
    if shutil.which("manim") is None and importlib.util.find_spec("manim") is None:
        pytest.fail("manim is not installed; CI must `pip install -e .[dev]` with manim deps")


def test_six_samples_render_with_current_prompts() -> None:
    _load("gepa_metrics")
    _load("gepa_invoke_agents")
    runner = _load("gepa_pipeline_runner")

    valset = yaml.safe_load(VALSET_YAML.read_text(encoding="utf-8"))
    candidate = _read_current_candidate()
    results = runner.run_valset(candidate, valset, quality="low")

    failed = [k for k, ok in results.items() if not ok]
    assert not failed, (
        f"regression guard: {len(failed)}/{len(results)} samples failed: {failed}. "
        "See per-sample stderr in the failed scene's render JSON. Inspect by "
        "running `pwsh samples/build-samples.ps1` (or .sh) locally."
    )
