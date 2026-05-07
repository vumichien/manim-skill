"""Unit tests for scripts/concat-xfade.py — filter graph generation only.

These tests do NOT invoke ffmpeg. They exercise build_filter_chain() which is a
pure function of (n, durations, transition_s, has_audio).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "concat-xfade.py"


def _load():
    spec = importlib.util.spec_from_file_location("concat_xfade", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m():
    return _load()


def test_filter_chain_2_inputs_with_audio(m) -> None:
    chain, vmap, amap = m.build_filter_chain(2, [4.0, 6.0], 0.7, has_audio=True)
    # One xfade for video, one acrossfade for audio
    assert vmap == "[v1]"
    assert amap == "[a1]"
    assert "xfade=transition=fade:duration=0.7:offset=3.3000" in chain
    assert "acrossfade=duration=0.7" in chain


def test_filter_chain_5_inputs_offsets(m) -> None:
    durations = [4.0, 6.0, 5.0, 3.0, 4.0]
    chain, vmap, amap = m.build_filter_chain(5, durations, 0.7, has_audio=True)
    assert vmap == "[v4]"
    assert amap == "[a4]"
    # Expected offsets: [4-0.7, 10-1.4, 15-2.1, 18-2.8] = [3.3, 8.6, 12.9, 15.2]
    assert "offset=3.3000" in chain
    assert "offset=8.6000" in chain
    assert "offset=12.9000" in chain
    assert "offset=15.2000" in chain


def test_filter_chain_no_audio(m) -> None:
    chain, vmap, amap = m.build_filter_chain(3, [5.0, 5.0, 5.0], 0.7, has_audio=False)
    assert vmap == "[v2]"
    assert amap == ""
    assert "acrossfade" not in chain
    assert chain.count("xfade") == 2


def test_filter_chain_offset_clamp(m) -> None:
    # First scene shorter than transition would yield negative offset; must clamp to 0.
    chain, vmap, _ = m.build_filter_chain(2, [0.5, 5.0], 0.7, has_audio=False)
    assert "offset=0.0000" in chain
    assert vmap == "[v1]"


def test_filter_chain_single_input(m) -> None:
    chain, vmap, amap = m.build_filter_chain(1, [5.0], 0.7, has_audio=True)
    assert chain == ""
    assert vmap == "[0:v]"
    assert amap == "[0:a]"


def test_xfade_filter_available_on_dev_box(m) -> None:
    # Dev environment has ffmpeg with xfade per phase 6 manual probe.
    # Skip cleanly if not present so the test is portable.
    if not m.has_xfade_filter():
        pytest.skip("ffmpeg xfade filter not available in this env")
    assert m.has_xfade_filter() is True
