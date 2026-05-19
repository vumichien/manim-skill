"""Smoke tests for scripts/gepa_adapter.py with a mocked pipeline runner."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
AGENTS = REPO / "agents"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def adapter_mod():
    _load("gepa_metrics")
    _load("gepa_invoke_agents")
    _load("gepa_pipeline_runner")
    return _load("gepa_adapter")


def test_split_prompt_extracts_frontmatter(adapter_mod):
    text = "---\nname: foo\ntools: A, B\n---\n# Body\n\nProse here.\n"
    fm, body = adapter_mod.split_prompt(text)
    assert fm == "---\nname: foo\ntools: A, B\n---\n"
    assert body.startswith("# Body")


def test_split_prompt_no_frontmatter(adapter_mod):
    text = "# Body\n\nProse.\n"
    fm, body = adapter_mod.split_prompt(text)
    assert fm == ""
    assert body == text


def test_join_prompt_round_trip(adapter_mod):
    text = "---\na: 1\n---\nbody\n"
    fm, body = adapter_mod.split_prompt(text)
    assert adapter_mod.join_prompt(fm, body) == text


def test_round_trip_on_real_agent_files(adapter_mod):
    for name in ("manim-researcher.md", "manim-planner.md", "manim-implementer.md"):
        p = AGENTS / name
        original = p.read_text(encoding="utf-8")
        fm, body = adapter_mod.split_prompt(original)
        assert fm.startswith("---\n"), f"{name}: expected leading frontmatter"
        assert fm.endswith("---\n"), f"{name}: expected trailing frontmatter delimiter"
        assert adapter_mod.join_prompt(fm, body) == original


def test_reflection_lm_guard_rejects_claude(adapter_mod):
    for bad in ("anthropic/claude-3.5-sonnet", "claude-3-opus", "Anthropic/Claude-3.5"):
        with pytest.raises(ValueError):
            adapter_mod.ManimSkillAdapter([], "run", reflection_lm=bad)


def test_reflection_lm_guard_accepts_openai(adapter_mod):
    a = adapter_mod.ManimSkillAdapter([], "run", reflection_lm="openai/gpt-4.1-mini")
    assert a.reflection_lm == "openai/gpt-4.1-mini"


def test_reflection_lm_guard_can_be_bypassed(adapter_mod):
    a = adapter_mod.ManimSkillAdapter([], "run", reflection_lm="claude-3-opus", allow_claude_reflection=True)
    assert a.reflection_lm == "claude-3-opus"


def test_evaluate_returns_evaluation_batch_with_scores(monkeypatch, adapter_mod):
    """evaluate() must conform to GEPA's API: returns EvaluationBatch."""
    from gepa_metrics import PipelineTrace, RenderResult

    def fake_run(candidate, topic, **kw):
        return PipelineTrace(
            topic=topic, storyboard_valid=True,
            scenes_total=2, scenes_rendered=1,
            render_results=(
                RenderResult(scene_id="scene_01", ok=True),
                RenderResult(scene_id="scene_02", ok=False, error_class="latex"),
            ),
        )

    monkeypatch.setattr(adapter_mod, "pipeline_run", fake_run)
    a = adapter_mod.ManimSkillAdapter([], "test-run", reflection_lm="openai/gpt-4.1-mini")
    cand = {"researcher": "R", "planner": "P", "implementer": "I"}
    batch = [{"input": "topic A"}, {"input": "topic B"}]
    eb = a.evaluate(batch, cand, capture_traces=True)
    assert len(eb.scores) == 2
    # schema(0.4) + render(0.3*0.5) + mathtex(0.2) + regression(0.1) = 0.85
    assert eb.scores[0] == pytest.approx(0.85)
    assert eb.trajectories is not None
    assert eb.trajectories[1].topic == "topic B"


def test_make_reflective_dataset_per_component(monkeypatch, adapter_mod):
    from gepa_metrics import PipelineTrace

    def fake_run(candidate, topic, **kw):
        return PipelineTrace(topic=topic, storyboard_valid=True, scenes_total=1, scenes_rendered=1)

    monkeypatch.setattr(adapter_mod, "pipeline_run", fake_run)
    a = adapter_mod.ManimSkillAdapter([], "test-run", reflection_lm="openai/gpt-4.1-mini")
    eb = a.evaluate([{"input": "t"}], {"researcher": "", "planner": "", "implementer": ""}, capture_traces=True)
    ds = a.make_reflective_dataset({}, eb, components_to_update=["researcher", "planner"])
    assert set(ds.keys()) == {"researcher", "planner"}
    assert len(ds["researcher"]) == 1
    entry = ds["researcher"][0]
    assert entry["Inputs"]["topic"] == "t"
    assert "Feedback" in entry
    assert "pareto_vector" in entry
    assert set(entry["pareto_vector"]) == {"schema", "render", "mathtex", "regression"}


def test_evaluate_with_reruns_records_variance(monkeypatch, adapter_mod):
    from gepa_metrics import PipelineTrace

    counter = {"i": 0}
    valid_seq = [True, False, True]

    def fake_run(candidate, topic, **kw):
        i = counter["i"]
        counter["i"] += 1
        return PipelineTrace(
            topic=topic,
            storyboard_valid=valid_seq[i % len(valid_seq)],
            scenes_total=1, scenes_rendered=1,
        )

    monkeypatch.setattr(adapter_mod, "pipeline_run", fake_run)
    a = adapter_mod.ManimSkillAdapter([], "test", reflection_lm="openai/gpt-4.1-mini", reruns=3)
    eb = a.evaluate([{"input": "t"}], {"researcher": "", "planner": "", "implementer": ""}, capture_traces=True)
    assert eb.trajectories[0].variance > 0.0
