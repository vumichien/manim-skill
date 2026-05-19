"""Unit tests for scripts/mathtex_check.py — silent-MathTex detector."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO / "scripts" / "mathtex_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mathtex_check", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mathtex_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_scan_mathtex_usage_detects_mathtex(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("from manim import *\nclass S(Scene):\n    def construct(self): self.add(MathTex('x^2'))\n")
    assert m.scan_mathtex_usage(scene) is True


def test_scan_mathtex_usage_detects_tex(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("self.play(Write(Tex('hi')))\n")
    assert m.scan_mathtex_usage(scene) is True


def test_scan_mathtex_usage_negative(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("self.add(Text('plain'))\n")
    assert m.scan_mathtex_usage(scene) is False


def test_scan_mathtex_usage_does_not_match_text(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    # `Text(` and `IntegerTex` should not trigger (word-boundary regex).
    scene.write_text("self.add(Text('hi'))\nself.add(IntegerTex('1'))\n")
    # `IntegerTex` ends in `Tex(` after a non-word boundary? No — `r` before `Tex` IS a word char,
    # so \b before MathTex|Tex requires a non-word char left. "rTex" → no match. Good.
    assert m.scan_mathtex_usage(scene) is False


def test_scan_mathtex_usage_missing_file(tmp_path: Path) -> None:
    m = _load_module()
    assert m.scan_mathtex_usage(tmp_path / "missing.py") is False


def test_check_mathtex_dry_run_present(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("MathTex('x')\n")
    result = m.check_mathtex(scene, None, dry_run=True)
    assert result == {
        "mathtex_present": True,
        "mathtex_suspected_empty": None,
        "black_pixel_ratio": None,
    }


def test_check_mathtex_dry_run_absent(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("Text('x')\n")
    result = m.check_mathtex(scene, None, dry_run=True)
    assert result == {
        "mathtex_present": False,
        "mathtex_suspected_empty": False,
        "black_pixel_ratio": None,
    }


def test_check_mathtex_missing_output(tmp_path: Path) -> None:
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("MathTex('x')\n")
    result = m.check_mathtex(scene, str(tmp_path / "missing.mp4"), dry_run=False)
    assert result["mathtex_present"] is True
    assert result["mathtex_suspected_empty"] is None
    assert result["black_pixel_ratio"] is None


def test_check_mathtex_absent_no_video(tmp_path: Path) -> None:
    """When MathTex not present, suspected_empty is False regardless of video presence."""
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("Text('x')\n")
    result = m.check_mathtex(scene, None, dry_run=False)
    # No video to inspect; we know MathTex is absent → suspected_empty = False.
    assert result["mathtex_present"] is False
    assert result["mathtex_suspected_empty"] is False


@pytest.mark.requires_manim
def test_frame_black_ratio_on_black_video(tmp_path: Path) -> None:
    """Generate a 1s all-black video via ffmpeg and verify ratio ~1.0."""
    import shutil
    import subprocess
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    m = _load_module()
    vp = tmp_path / "black.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1",
            "-pix_fmt", "yuv420p", str(vp),
        ],
        check=True, capture_output=True,
    )
    ratio = m._frame_black_ratio(vp, 0.5)
    assert ratio is not None and ratio > 0.99


@pytest.mark.requires_manim
def test_check_mathtex_suspected_empty_on_black_video(tmp_path: Path) -> None:
    """End-to-end: scene mentions MathTex + video is all black → suspected_empty True."""
    import shutil
    import subprocess
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")
    m = _load_module()
    scene = tmp_path / "scene.py"
    scene.write_text("self.add(MathTex('\\\\frac{1}{2}'))\n")
    vp = tmp_path / "black.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1",
            "-pix_fmt", "yuv420p", str(vp),
        ],
        check=True, capture_output=True,
    )
    result = m.check_mathtex(scene, str(vp), dry_run=False)
    assert result["mathtex_present"] is True
    assert result["mathtex_suspected_empty"] is True
    assert result["black_pixel_ratio"] is not None and result["black_pixel_ratio"] > 0.99
