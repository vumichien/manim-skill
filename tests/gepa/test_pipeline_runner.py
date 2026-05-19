"""Smoke tests for scripts/gepa_pipeline_runner.py using a mock transport."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def runner():
    _load("gepa_metrics")
    _load("gepa_invoke_agents")
    return _load("gepa_pipeline_runner")


@pytest.fixture
def transport_mod():
    return _load("gepa_invoke_agents")


def test_extract_first_yaml_block(transport_mod):
    text = "before\n```yaml\nmeta:\n  schema_version: '0.2.0'\n```\nafter"
    out = transport_mod._extract_first_code_block(text, transport_mod.YAML_BLOCK_RE)
    assert out is not None
    assert "schema_version" in out


def test_extract_no_block_returns_none(transport_mod):
    assert transport_mod._extract_first_code_block("plain text", transport_mod.YAML_BLOCK_RE) is None


class _MockTransport:
    """In-memory transport returning a pre-built storyboard + 1 scene."""

    def __init__(self, storyboard_yaml: str, scene_code: str | None = None):
        self.storyboard_yaml = storyboard_yaml
        self.scene_code = scene_code

    def run(self, candidate, topic, work_dir):
        from gepa_invoke_agents import TransportResult
        sb = work_dir / "storyboard.yaml"
        sb.write_text(self.storyboard_yaml, encoding="utf-8")
        scenes: list[Path] = []
        if self.scene_code:
            sp = work_dir / "scene_01.py"
            sp.write_text(self.scene_code, encoding="utf-8")
            scenes.append(sp)
        return TransportResult(sb, tuple(scenes))


def _valid_storyboard_yaml() -> str:
    """Reuse sample 01 (Pythagoras) — known to validate against the schema."""
    sb = REPO / "samples" / "01-pythagoras-2d" / "storyboard.yaml"
    return sb.read_text(encoding="utf-8")


def test_run_with_mock_transport_storyboard_invalid_when_yaml_broken(runner, tmp_path):
    cand = {"researcher": "r", "planner": "p", "implementer": "i"}
    mock = _MockTransport(storyboard_yaml="not: valid: yaml: storyboard: at all")
    trace = runner.run(cand, "test topic", transport=mock, dry_run=True, run_id="test", candidate_idx=0)
    assert trace.storyboard_valid is False
    assert trace.scenes_total == 0


def test_run_transport_failure_returns_zero_trace(runner, tmp_path):
    from gepa_invoke_agents import TransportResult

    class _BrokenTransport:
        def run(self, candidate, topic, work_dir):
            return TransportResult(None, (), "transport boom")

    cand = {"researcher": "r", "planner": "p", "implementer": "i"}
    trace = runner.run(cand, "test", transport=_BrokenTransport(), run_id="test", candidate_idx=1)
    assert trace.storyboard_valid is False
    assert "transport boom" in trace.schema_errors[0]
    assert trace.scenes_total == 0
    assert trace.scenes_rendered == 0


def test_scene_class_name_default(runner, tmp_path):
    f = tmp_path / "scene_01.py"
    f.write_text("class Scene01(Scene):\n    pass\n", encoding="utf-8")
    assert runner._scene_class_name(f) == "Scene01"


def test_scene_class_name_threed(runner, tmp_path):
    f = tmp_path / "scene_02.py"
    f.write_text("class Cubey(ThreeDScene):\n    pass\n", encoding="utf-8")
    assert runner._scene_class_name(f) == "Cubey"


def test_run_with_empty_storyboard_yaml_returns_zero_trace(runner):
    """Transport produced storyboard.yaml that parses to None (empty file).

    Regression for crash observed mid-GEPA-run: `data.get('scenes', [])`
    raised AttributeError when safe_load returned None.
    """
    cand = {"researcher": "r", "planner": "p", "implementer": "i"}
    for content in ("", "   \n", "# just a comment\n"):
        mock = _MockTransport(storyboard_yaml=content)
        trace = runner.run(cand, "empty", transport=mock, dry_run=True, run_id="test", candidate_idx=9)
        assert trace.storyboard_valid is False
        assert trace.scenes_total == 0


def test_scenes_from_storyboard_handles_none(runner, tmp_path):
    """Direct unit test for the guard added to _scenes_from_storyboard."""
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert runner._scenes_from_storyboard(p) == 0
    p.write_text("scenes: not-a-list\n", encoding="utf-8")
    assert runner._scenes_from_storyboard(p) == 0
    p.write_text("scenes:\n  - id: s1\n  - id: s2\n", encoding="utf-8")
    assert runner._scenes_from_storyboard(p) == 2


def test_run_storyboard_valid_with_no_scene_files(runner):
    """A valid storyboard but transport gave no scene files → render results empty."""
    cand = {"researcher": "r", "planner": "p", "implementer": "i"}
    mock = _MockTransport(storyboard_yaml=_valid_storyboard_yaml())
    trace = runner.run(cand, "smoke", transport=mock, dry_run=True, run_id="test", candidate_idx=2)
    assert trace.storyboard_valid is True
    assert trace.scenes_total >= 1
    assert trace.scenes_rendered == 0
    assert trace.render_results == ()
