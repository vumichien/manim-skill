"""Tests for scripts/agents_override_path.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("agents_override_path", SCRIPTS / "agents_override_path.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agents_override_path"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_falls_back_to_plugin_baseline(monkeypatch, tmp_path):
    m = _load()
    monkeypatch.setattr(m, "get_override_dir", lambda: tmp_path / "noexist")
    p = m.resolve_agent("manim-researcher")
    assert p == REPO / "agents" / "manim-researcher.md"


def test_resolve_prefers_override(monkeypatch, tmp_path):
    m = _load()
    override = tmp_path / "override"
    override.mkdir()
    (override / "manim-researcher.md").write_text("OVERRIDE", encoding="utf-8")
    monkeypatch.setattr(m, "get_override_dir", lambda: override)
    p = m.resolve_agent("manim-researcher")
    assert p == override / "manim-researcher.md"
    assert p.read_text(encoding="utf-8") == "OVERRIDE"


def test_resolve_appends_md(monkeypatch, tmp_path):
    m = _load()
    monkeypatch.setattr(m, "get_override_dir", lambda: tmp_path / "noexist")
    p = m.resolve_agent("manim-planner")
    assert p.name == "manim-planner.md"


def test_ensure_override_dir_creates(monkeypatch, tmp_path):
    m = _load()
    target = tmp_path / "subdir" / "agents-override"
    monkeypatch.setattr(m, "get_override_dir", lambda: target)
    out = m.ensure_override_dir()
    assert out == target
    assert out.exists() and out.is_dir()


def test_get_override_dir_windows(monkeypatch):
    m = _load()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("USERPROFILE", "C:/users/test")
    d = m.get_override_dir()
    assert ".manim-skill" in str(d).replace("\\", "/")


def test_get_override_dir_posix_xdg(monkeypatch):
    m = _load()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    d = m.get_override_dir()
    assert "/tmp/xdg/manim-skill" in str(d).replace("\\", "/") or "manim-skill" in str(d)
