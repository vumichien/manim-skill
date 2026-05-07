"""Each samples/NN-*/ ships a valid storyboard + a syntactically-clean scene.py."""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SAMPLES = REPO / "samples"
VALIDATOR = REPO / "scripts" / "validate-storyboard.py"


def _sample_dirs() -> list[Path]:
    return sorted(p for p in SAMPLES.iterdir() if p.is_dir() and p.name[:2].isdigit())


@pytest.mark.parametrize("sample_dir", _sample_dirs(), ids=lambda p: p.name)
def test_sample_storyboard_validates(sample_dir: Path) -> None:
    yaml_path = sample_dir / "storyboard.yaml"
    assert yaml_path.exists(), f"missing {yaml_path}"
    res = subprocess.run(
        [sys.executable, str(VALIDATOR), str(yaml_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"{yaml_path}:\n{res.stderr}"


@pytest.mark.parametrize("sample_dir", _sample_dirs(), ids=lambda p: p.name)
def test_sample_scene_compiles(sample_dir: Path) -> None:
    scene_py = sample_dir / "scene.py"
    assert scene_py.exists(), f"missing {scene_py}"
    py_compile.compile(str(scene_py), doraise=True)
