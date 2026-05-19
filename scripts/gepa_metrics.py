"""Composite metric for GEPA prompt optimization.

Returns `(float_score, diagnostic_str)` from a pipeline-run trace. GEPA reads
both — the scalar drives candidate selection, the natural-language diagnostic
drives the reflection LM. Diagnostic quality drives reflection quality, so we
spend effort here, not just on the number.

Weights (v1, from plan §Locked decisions):
  schema      0.4   (nothing downstream works without a valid storyboard)
  render      0.3   (per-scene render success rate)
  mathtex     0.2   (penalize silent empty-MathTex frames)
  regression  0.1   (don't break the 6 reference samples)

A Pareto-vector form keeps candidates strong on a single axis even if total
drops. v2 metrics (e.g. visual quality) plug in via `add_metric`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

WEIGHTS: dict[str, float] = {
    "schema": 0.4,
    "render": 0.3,
    "mathtex": 0.2,
    "regression": 0.1,
}
DIAGNOSTIC_LINE_CAP = 80


@dataclass(frozen=True)
class RenderResult:
    """Per-scene render outcome, mirroring scripts/render.py JSON contract."""
    scene_id: str
    ok: bool
    error_class: str | None = None
    stderr_tail: str = ""
    mathtex_present: bool = False
    mathtex_suspected_empty: bool | None = None


@dataclass(frozen=True)
class PipelineTrace:
    """A single pipeline-run outcome, consumed by the metric scorers."""
    topic: str
    storyboard_valid: bool
    schema_errors: tuple[str, ...] = ()
    scenes_total: int = 0
    scenes_rendered: int = 0
    render_results: tuple[RenderResult, ...] = ()
    regression: dict[str, bool] = field(default_factory=dict)

    @property
    def mathtex_total(self) -> int:
        return sum(1 for r in self.render_results if r.mathtex_present)

    @property
    def mathtex_empty(self) -> int:
        return sum(1 for r in self.render_results if r.mathtex_suspected_empty)


def score_schema(trace: PipelineTrace) -> float:
    return 1.0 if trace.storyboard_valid else 0.0


def score_render(trace: PipelineTrace) -> float:
    if trace.scenes_total <= 0:
        return 0.0
    return trace.scenes_rendered / trace.scenes_total


def score_mathtex(trace: PipelineTrace) -> float:
    total = trace.mathtex_total
    if total == 0:
        return 1.0
    return 1.0 - (trace.mathtex_empty / total)


def score_regression(trace: PipelineTrace) -> float:
    if not trace.regression:
        return 1.0
    passed = sum(1 for ok in trace.regression.values() if ok)
    return passed / len(trace.regression)


def pareto_vector(trace: PipelineTrace) -> dict[str, float]:
    """Per-axis scores for frontier maintenance."""
    return {
        "schema": score_schema(trace),
        "render": score_render(trace),
        "mathtex": score_mathtex(trace),
        "regression": score_regression(trace),
    }


def format_for_reflection(trace: PipelineTrace) -> str:
    """Bullet diagnostic the reflection LM reads. Cap at DIAGNOSTIC_LINE_CAP lines.

    Schema errors are emitted first (highest weight). MathTex empties and
    regression failures follow, with scene/sample identifiers.
    """
    lines: list[str] = [f"topic: {trace.topic}"]
    vec = pareto_vector(trace)
    lines.append(
        f"scores: schema={vec['schema']:.2f} render={vec['render']:.2f} "
        f"mathtex={vec['mathtex']:.2f} regression={vec['regression']:.2f}"
    )
    if trace.schema_errors:
        lines.append(f"schema errors ({len(trace.schema_errors)}):")
        for e in trace.schema_errors[:20]:
            lines.append(f"  - {e}")
    if trace.scenes_total:
        lines.append(f"render: {trace.scenes_rendered}/{trace.scenes_total} scenes ok")
    err_counts: dict[str, int] = {}
    for r in trace.render_results:
        if not r.ok and r.error_class:
            err_counts[r.error_class] = err_counts.get(r.error_class, 0) + 1
    if err_counts:
        tally = ", ".join(f"{k}={v}" for k, v in sorted(err_counts.items()))
        lines.append(f"error_class tally: {tally}")
    mathtex_empty_scenes = [r.scene_id for r in trace.render_results if r.mathtex_suspected_empty]
    if mathtex_empty_scenes:
        lines.append(f"mathtex empty in: {', '.join(mathtex_empty_scenes)}")
    failed_samples = [k for k, ok in trace.regression.items() if not ok]
    if failed_samples:
        lines.append(f"regression failed: {', '.join(failed_samples)}")
    return "\n".join(lines[:DIAGNOSTIC_LINE_CAP])


BASE_KEYS = ("schema", "render", "mathtex", "regression")


def composite_score(trace: PipelineTrace) -> tuple[float, str]:
    """Weighted scalar score + reflection-ready diagnostic.

    Total = WEIGHTS['schema']*schema + WEIGHTS['render']*render +
            WEIGHTS['mathtex']*mathtex + WEIGHTS['regression']*regression
    Plus any v2 metrics in METRIC_REGISTRY (weight × fn(trace)).
    """
    vec = pareto_vector(trace)
    total = sum(WEIGHTS[k] * vec[k] for k in BASE_KEYS)
    total += sum(weight * fn(trace) for fn, weight in METRIC_REGISTRY.values())
    return round(total, 4), format_for_reflection(trace)


# v2 hook: callers can register additional metrics. Each metric is
# (callable_returning_float, weight). Weights of registered metrics ADD on top
# of the base 1.0 — caller responsibility to keep total sane.
METRIC_REGISTRY: dict[str, tuple[Callable[[PipelineTrace], float], float]] = {}


def add_metric(name: str, fn: Callable[[PipelineTrace], float], weight: float) -> None:
    """Register a v2 metric. Unused by v1 GEPA path; reserved hook."""
    if name in WEIGHTS:
        raise ValueError(f"'{name}' is a built-in metric and cannot be overridden")
    METRIC_REGISTRY[name] = (fn, weight)
    WEIGHTS[name] = weight
