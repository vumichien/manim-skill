"""Unit tests for scripts/gepa_metrics.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = REPO / "scripts" / "gepa_metrics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gepa_metrics", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gepa_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def m():
    mod = _load_module()
    # Reset registry between tests (module is reloaded per fixture).
    mod.METRIC_REGISTRY.clear()
    for k in list(mod.WEIGHTS):
        if k not in {"schema", "render", "mathtex", "regression"}:
            mod.WEIGHTS.pop(k)
    return mod


def _trace(m, **kw):
    """Build a PipelineTrace with defaults."""
    return m.PipelineTrace(
        topic=kw.get("topic", "test topic"),
        storyboard_valid=kw.get("storyboard_valid", True),
        schema_errors=tuple(kw.get("schema_errors", ())),
        scenes_total=kw.get("scenes_total", 3),
        scenes_rendered=kw.get("scenes_rendered", 3),
        render_results=tuple(kw.get("render_results", ())),
        regression=kw.get("regression", {}),
    )


def test_all_pass_score_is_one(m):
    t = _trace(m)
    score, diag = m.composite_score(t)
    assert score == pytest.approx(1.0)
    assert "test topic" in diag


def test_schema_failure_costs_0_4(m):
    t = _trace(m, storyboard_valid=False, schema_errors=("scenes/0/id missing",))
    score, _ = m.composite_score(t)
    # schema=0, render=1, mathtex=1, regression=1 → 0 + 0.3 + 0.2 + 0.1 = 0.6
    assert score == pytest.approx(0.6)


def test_partial_render_yields_fractional(m):
    t = _trace(m, scenes_total=4, scenes_rendered=2)
    # schema=1, render=0.5, mathtex=1, regression=1 → 0.4 + 0.15 + 0.2 + 0.1 = 0.85
    score, _ = m.composite_score(t)
    assert score == pytest.approx(0.85)


def test_mathtex_empty_costs_proportionally(m):
    r1 = m.RenderResult(scene_id="scene_01", ok=True, mathtex_present=True, mathtex_suspected_empty=False)
    r2 = m.RenderResult(scene_id="scene_02", ok=True, mathtex_present=True, mathtex_suspected_empty=True)
    t = _trace(m, scenes_total=2, scenes_rendered=2, render_results=(r1, r2))
    # schema=1, render=1, mathtex=0.5, regression=1 → 0.4 + 0.3 + 0.1 + 0.1 = 0.9
    score, _ = m.composite_score(t)
    assert score == pytest.approx(0.9)


def test_regression_partial_costs(m):
    t = _trace(m, regression={"01": True, "02": False, "03": True, "04": True, "05": True, "06": True})
    # 5/6 → 0.4 + 0.3 + 0.2 + 0.0833 ≈ 0.9833
    score, _ = m.composite_score(t)
    assert score == pytest.approx(0.4 + 0.3 + 0.2 + 0.1 * (5 / 6), abs=1e-3)


def test_pareto_vector_keys(m):
    t = _trace(m)
    v = m.pareto_vector(t)
    assert set(v.keys()) == {"schema", "render", "mathtex", "regression"}
    assert all(0.0 <= x <= 1.0 for x in v.values())


def test_diagnostic_mentions_schema_errors(m):
    t = _trace(m, storyboard_valid=False, schema_errors=("scenes/0/id: missing", "meta/total_duration_s: drift"))
    _, diag = m.composite_score(t)
    assert "schema errors" in diag
    assert "scenes/0/id: missing" in diag


def test_diagnostic_caps_at_80_lines(m):
    many_errors = tuple(f"error_{i}" for i in range(500))
    t = _trace(m, storyboard_valid=False, schema_errors=many_errors)
    _, diag = m.composite_score(t)
    assert len(diag.splitlines()) <= 80


def test_diagnostic_mentions_mathtex_empty_scenes(m):
    rr = (
        m.RenderResult(scene_id="scene_03", ok=True, mathtex_present=True, mathtex_suspected_empty=True),
    )
    t = _trace(m, scenes_total=1, scenes_rendered=1, render_results=rr)
    _, diag = m.composite_score(t)
    assert "scene_03" in diag


def test_add_metric_rejects_builtin_name(m):
    with pytest.raises(ValueError):
        m.add_metric("schema", lambda t: 1.0, 0.5)


def test_add_metric_stores_callable(m):
    called = []

    def my_metric(_t):
        called.append(True)
        return 1.0

    m.add_metric("visual", my_metric, 0.5)
    t = _trace(m)
    score, _ = m.composite_score(t)
    assert called  # registry metric was invoked
    assert score == pytest.approx(1.5)  # 1.0 base + 0.5 * 1.0


def test_score_render_zero_scenes(m):
    t = _trace(m, scenes_total=0, scenes_rendered=0)
    assert m.score_render(t) == 0.0


def test_score_mathtex_no_mathtex_present(m):
    """When no scenes use MathTex, score is 1.0 (no penalty)."""
    t = _trace(m, scenes_total=1, scenes_rendered=1, render_results=())
    assert m.score_mathtex(t) == 1.0
