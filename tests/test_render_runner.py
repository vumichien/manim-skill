"""Render runner: JSON contract shape + error classifier unit tests + (optional) live render."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RENDER_PY = REPO / "scripts" / "render.py"
FIXTURES = REPO / "tests" / "fixtures"


def _load_render_module():
    spec = importlib.util.spec_from_file_location("render", RENDER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ('NameError: name "Cricle" is not defined', "name"),
        ("NameError: name 'Foo' is not defined",    "name"),
        ("ModuleNotFoundError: No module named 'x'", "import"),
        ("TypeError: unexpected kwarg",              "type"),
        ("LaTeX returned non-zero status",           "latex"),
        ("xelatex command not found",               "latex"),
        ("totally unrelated noise",                  "other"),
    ],
)
def test_classify(stderr: str, expected: str) -> None:
    render = _load_render_module()
    assert render.classify(stderr) == expected


def test_missing_scene_file_returns_structured_error(tmp_path: Path) -> None:
    res = subprocess.run(
        [
            sys.executable, str(RENDER_PY),
            "--scene-file", str(tmp_path / "missing.py"),
            "--class-name", "X",
            "--out-dir", str(tmp_path),
            "--dry-run",
        ],
        capture_output=True, text=True,
    )
    assert res.returncode == 2
    payload = json.loads(res.stdout)
    assert payload["ok"] is False
    assert "scene file not found" in payload["stderr_tail"]
    assert payload["error_class"] == "other"


@pytest.mark.requires_manim
def test_hello_scene_dry_run(tmp_path: Path) -> None:
    """Live test: passes only when `manim` is importable in the test venv."""
    if shutil.which("manim") is None and importlib.util.find_spec("manim") is None:
        pytest.skip("manim not installed in this environment")
    res = subprocess.run(
        [
            sys.executable, str(RENDER_PY),
            "--scene-file", str(FIXTURES / "hello_scene.py"),
            "--class-name", "HelloScene",
            "--quality", "low",
            "--out-dir", str(tmp_path),
            "--dry-run",
        ],
        capture_output=True, text=True, timeout=120,
    )
    payload = json.loads(res.stdout)
    assert payload["ok"] is True, f"dry-run failed: {payload['stderr_tail']}"
    assert payload["render_time_s"] < 60
