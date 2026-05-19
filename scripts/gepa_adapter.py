"""GEPA adapter bridging the manim-skill pipeline to gepa.optimize.

Conforms to `gepa.core.adapter.GEPAAdapter`:
  - evaluate(batch, candidate, capture_traces) -> EvaluationBatch
  - make_reflective_dataset(candidate, eval_batch, components_to_update) -> dict

Components GEPA optimizes (== keys of `candidate` dict):
  - researcher : agents/manim-researcher.md body
  - planner    : agents/manim-planner.md body
  - implementer: agents/manim-implementer.md body

Invariants:
  - YAML frontmatter is frozen at the optimize-prompts.py boundary. The
    candidate dict GEPA sees holds prose-body only; frontmatter is
    re-attached on write.
  - Reflection LM family must differ from candidate-execution LM family
    (no Claude→Claude self-reflection by default). The CLI has an explicit
    --allow-claude-reflection flag that bypasses this for users who want
    Claude CLI reflection on their subscription — they've accepted the bias.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import stdev
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gepa_metrics import PipelineTrace, composite_score, pareto_vector  # noqa: E402
from gepa_pipeline_runner import run as pipeline_run  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFLECTION_LM = "openai/gpt-4.1-mini"
FORBIDDEN_REFLECTION_PREFIXES = ("anthropic/", "claude-", "claude/")
CLAUDE_REFLECTION_TIMEOUT_S = 600
# Default Claude model for the CLI reflection LM. Sonnet 4.6 keeps the workflow
# accessible to standard plans; override via `--claude-model` on optimize-prompts.
DEFAULT_CLAUDE_CLI_MODEL = "claude-sonnet-4-6"


@dataclass
class _EvalRecord:
    """Internal trajectory the adapter caches per example for reflection."""
    topic: str
    trace: PipelineTrace
    diagnostic: str
    variance: float = 0.0


@dataclass
class EvaluationBatchLite:
    """Lightweight stand-in for gepa.EvaluationBatch (loaded lazily)."""
    outputs: list[Any] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    trajectories: list[_EvalRecord] | None = None
    objective_scores: list[dict[str, float]] | None = None


def _gepa_evaluation_batch():
    """Return the real gepa.EvaluationBatch class. Lazy import."""
    from gepa import EvaluationBatch
    return EvaluationBatch


def split_prompt(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :]


def join_prompt(frontmatter: str, body: str) -> str:
    return frontmatter + body


def validate_reflection_lm(name: str, *, allow_claude: bool = False) -> None:
    """Reject Anthropic/Claude reflection LMs unless explicitly allowed."""
    if allow_claude:
        return
    lower = name.lower()
    for bad in FORBIDDEN_REFLECTION_PREFIXES:
        if lower.startswith(bad):
            raise ValueError(
                f"reflection_lm '{name}' is in the Claude family. Pass "
                "allow_claude=True (or --allow-claude-reflection on the CLI) "
                "to bypass this guard if you've accepted the self-bias trade-off."
            )


class ClaudeCliReflectionLM:
    """Wrap `claude --print` as a callable for gepa.optimize's reflection_lm.

    Defaults to `claude-sonnet-4-6` so the GEPA workflow stays accessible on
    standard Claude plans; override with `model=` or `--claude-model` on the
    CLI if you want Opus.
    """

    def __init__(
        self,
        claude_bin: str = "claude",
        *,
        model: str = DEFAULT_CLAUDE_CLI_MODEL,
        extra_args: list[str] | None = None,
    ) -> None:
        if shutil.which(claude_bin) is None:
            raise SystemExit(
                f"`{claude_bin}` not found on PATH. Install Claude Code "
                "(https://claude.com/code) or pass --reflection-lm <litellm-model>."
            )
        self.claude_bin = claude_bin
        self.model = model
        self.extra_args = extra_args or []

    def __call__(self, prompt: str | list[dict[str, Any]]) -> str:
        # GEPA may pass a list-of-messages instead of a string; flatten it.
        if isinstance(prompt, list):
            prompt = "\n\n".join(
                f"[{m.get('role', 'user')}]\n{m.get('content', '')}" for m in prompt
            )
        # Pass prompt via stdin, NOT as a CLI argument. Reflection prompts
        # grow past 32KB once the reflective dataset accumulates, and Windows'
        # CreateProcess arg-length limit (~32K chars) makes the child exit 1
        # with empty stderr — silent failure that wasted a full run before.
        cmd = [
            self.claude_bin,
            "--print",
            "--dangerously-skip-permissions",
            "--model", self.model,
            *self.extra_args,
        ]
        try:
            proc = subprocess.run(  # noqa: S603 — explicit arg list, no shell
                cmd, input=prompt, capture_output=True, text=True,
                timeout=CLAUDE_REFLECTION_TIMEOUT_S, encoding="utf-8",
            )
        except subprocess.SubprocessError as exc:
            raise RuntimeError(f"claude --print failed: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude --print exit {proc.returncode}: "
                f"stderr={proc.stderr[:500]!r} stdout_tail={proc.stdout[-200:]!r}"
            )
        return proc.stdout


class ManimSkillAdapter:
    """GEPAAdapter implementation for manim-skill.

    Note: not inheriting from `gepa.GEPAAdapter` directly so the module remains
    importable without the `[dev]` extras (matches gepa_metrics, runner).
    GEPA's Protocol-based duck typing accepts us regardless.
    """

    COMPONENTS = ("researcher", "planner", "implementer")
    # GEPA's reflective_mutation reads this attribute. None = use default
    # instruction proposal driven by the reflection LM.
    propose_new_texts = None

    def __init__(
        self,
        valset: list[dict],
        run_id: str,
        *,
        reflection_lm: str = DEFAULT_REFLECTION_LM,
        reruns: int = 1,
        quality: str = "low",
        transport=None,
        allow_claude_reflection: bool = False,
    ) -> None:
        validate_reflection_lm(reflection_lm, allow_claude=allow_claude_reflection)
        self.valset = valset
        self.run_id = run_id
        self.reflection_lm = reflection_lm
        self.reruns = max(1, reruns)
        self.quality = quality
        self.transport = transport
        self._candidate_idx = 0
        self._last_records: dict[int, _EvalRecord] = {}

    @staticmethod
    def normalize_candidate(candidate: dict[str, str]) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for k, v in candidate.items():
            fm, body = split_prompt(v)
            out[k] = {"frontmatter": fm, "body": body}
        return out

    @staticmethod
    def restore_candidate(normalized: dict[str, dict[str, str]]) -> dict[str, str]:
        return {k: join_prompt(v["frontmatter"], v["body"]) for k, v in normalized.items()}

    def evaluate(self, batch, candidate, capture_traces=False):
        """Per the GEPAAdapter protocol. Returns gepa.EvaluationBatch."""
        EvaluationBatch = _gepa_evaluation_batch()
        outputs: list[dict[str, Any]] = []
        scores: list[float] = []
        records: list[_EvalRecord] = []
        for example in batch:
            topic = example.get("input") if isinstance(example, dict) else str(example)
            topic = topic or ""
            run_scores: list[float] = []
            last_trace: PipelineTrace | None = None
            last_diag = ""
            for _ in range(self.reruns):
                self._candidate_idx += 1
                trace = pipeline_run(
                    candidate, topic,
                    transport=self.transport,
                    quality=self.quality,
                    run_id=self.run_id,
                    candidate_idx=self._candidate_idx,
                )
                score, diag = composite_score(trace)
                run_scores.append(score)
                last_trace = trace
                last_diag = diag
            variance = stdev(run_scores) if len(run_scores) > 1 else 0.0
            avg_score = sum(run_scores) / len(run_scores)
            rec = _EvalRecord(topic=topic, trace=last_trace, diagnostic=last_diag, variance=variance)
            records.append(rec)
            outputs.append({
                "topic": topic,
                "storyboard_valid": last_trace.storyboard_valid,
                "scenes_rendered": f"{last_trace.scenes_rendered}/{last_trace.scenes_total}",
                "mathtex_total": last_trace.mathtex_total,
                "mathtex_empty": last_trace.mathtex_empty,
            })
            scores.append(avg_score)
        return EvaluationBatch(
            outputs=outputs,
            scores=scores,
            trajectories=records if capture_traces else None,
        )

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch,
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        """Build {component_name: [{Inputs, Generated Outputs, Feedback}, ...]}.

        Same feedback text for every component for now — GEPA's instruction
        proposer picks the one being mutated. The diagnostic already names
        which axes failed (schema, render, mathtex), which is enough signal.
        """
        out: dict[str, list[dict[str, Any]]] = {c: [] for c in components_to_update}
        records: list[_EvalRecord] = eval_batch.trajectories or []
        for rec, output, score in zip(records, eval_batch.outputs, eval_batch.scores, strict=False):
            entry = {
                "Inputs": {"topic": rec.topic},
                "Generated Outputs": {
                    "scenes_rendered": output.get("scenes_rendered"),
                    "storyboard_valid": output.get("storyboard_valid"),
                    "mathtex_empty": output.get("mathtex_empty"),
                },
                "Feedback": rec.diagnostic,
                "score": round(score, 4),
                "pareto_vector": pareto_vector(rec.trace),
                "variance": round(rec.variance, 4),
            }
            for c in components_to_update:
                out[c].append(entry)
        return out
