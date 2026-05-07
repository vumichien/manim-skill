"""Unit tests for shared chrome helpers (template at skills/manim-video/references)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "skills" / "manim-video" / "references" / "shared-chrome-template.py"


def _load_template():
    spec = importlib.util.spec_from_file_location("shared_chrome_template", TEMPLATE)
    if spec is None or spec.loader is None:
        pytest.skip(f"could not load template at {TEMPLATE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def chrome():
    return _load_template()


def test_chunk_captions_basic(chrome) -> None:
    text = " ".join(["word"] * 24)
    out = chrome.chunk_captions(text, total_s=12.0, words_per_chunk=8)
    assert len(out) == 3
    # Equal word counts -> equal time slices (each 4s).
    for i, (chunk_text, start, end) in enumerate(out):
        assert chunk_text.split() == ["word"] * 8
        assert end - start == pytest.approx(4.0, abs=0.01)
        assert start == pytest.approx(i * 4.0, abs=0.01)
    # Last chunk ends exactly at total_s.
    assert out[-1][2] == pytest.approx(12.0)


def test_chunk_captions_short_text(chrome) -> None:
    out = chrome.chunk_captions("hello world", total_s=5.0, words_per_chunk=10)
    assert len(out) == 1
    text, start, end = out[0]
    assert text == "hello world"
    assert start == 0.0
    assert end == pytest.approx(5.0)


def test_chunk_captions_zero_duration(chrome) -> None:
    out = chrome.chunk_captions("hello world", total_s=0.0, words_per_chunk=10)
    assert len(out) == 1
    text, start, end = out[0]
    assert text == "hello world"
    assert start == 0.0
    assert end == 0.0


def test_chunk_captions_empty(chrome) -> None:
    assert chrome.chunk_captions("", total_s=10.0) == []


def test_palette_keys(chrome) -> None:
    assert set(chrome.PALETTE.keys()) == {"primary", "accent", "warn", "bg"}
    for v in chrome.PALETTE.values():
        assert v.startswith("#") and len(v) == 7
