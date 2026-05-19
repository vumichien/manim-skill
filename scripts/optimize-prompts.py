#!/usr/bin/env python3
"""GEPA prompt-optimization CLI (maintainer / power-user tool).

Reads trainset + valset YAML, loads baseline agent prompts from
`agents/_baseline/`, runs GEPA's `optimize`, writes the best candidate back
to the chosen output directory while preserving each agent's frontmatter.

Examples:
  python scripts/optimize-prompts.py \
      --trainset tests/gepa/trainset.yaml \
      --valset   tests/gepa/valset.yaml \
      --budget 50 --reflection-lm openai/gpt-4.1-mini \
      --output agents/ --yes

  # User-mode (writes to per-user override dir):
  python scripts/optimize-prompts.py --user --budget 20 --yes
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import sys
from pathlib import Path

import yaml

# Force UTF-8 on stdout/stderr so GEPA's progress logging doesn't crash on
# non-ASCII content (e.g. math `≤`, em-dash, Greek letters in candidate text)
# under Windows JA locale (cp932). Wasted a full GEPA run before this guard.
for _stream in ("stdout", "stderr"):
    _s = getattr(sys, _stream, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, AttributeError):
            pass

def _patch_gepa_logger_for_utf8() -> None:
    """Patch gepa.logging.logger.Logger so its run_log files open as UTF-8.

    GEPA opens its run_log.txt with the default codec (cp932 on JA Windows),
    which crashes the moment a Unicode math symbol lands in a candidate. We
    rewrap the file handles in TextIOWrappers that re-encode to UTF-8.
    """
    try:
        import io
        from gepa.logging import logger as gepa_logger
    except ImportError:
        return
    orig_init = gepa_logger.Logger.__init__

    def _utf8_init(self, filename, mode="a"):
        orig_init(self, filename, mode)
        for attr in ("file_handle", "file_handle_stderr"):
            fh = getattr(self, attr)
            try:
                fh.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                # File was opened without underlying buffer-aware codec —
                # close it and reopen with explicit encoding.
                fh.close()
                target = filename if attr == "file_handle" else filename.replace(
                    "run_log.", "run_log_stderr."
                )
                setattr(self, attr, io.open(target, mode, encoding="utf-8", errors="replace"))

    gepa_logger.Logger.__init__ = _utf8_init  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents_override_path import ensure_override_dir  # noqa: E402
from gepa_adapter import (  # noqa: E402
    DEFAULT_REFLECTION_LM,
    ClaudeCliReflectionLM,
    ManimSkillAdapter,
    join_prompt,
    split_prompt,
)
from gepa_invoke_agents import ClaudeCliTransport, LitellmTransport  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "agents" / "_baseline"
AGENTS_DIR = REPO_ROOT / "agents"
RUNS_DIR = REPO_ROOT / "plans" / "gepa-runs"
AGENT_NAMES = ("manim-researcher", "manim-planner", "manim-implementer")

# Rough cost model: per-call avg-tokens × $ / 1k tokens. Conservative side.
# gpt-4.1-mini Jan 2026 list prices: ~$0.40 in / $1.60 out / 1M tokens.
TOKENS_PER_PIPELINE_CALL = 4000
USD_PER_KTOK_IO = 0.001  # blended in+out, conservative


def _load_yaml_list(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"{path}: expected a YAML list, got {type(data).__name__}")
    return data


def _load_baseline_candidate() -> dict[str, str]:
    cand: dict[str, str] = {}
    for short in AGENT_NAMES:
        p = BASELINE_DIR / f"{short}.md"
        if not p.exists():
            raise SystemExit(f"baseline missing: {p}. Run setup step from phase-06.")
        cand[short.replace("manim-", "")] = p.read_text(encoding="utf-8")
    return cand


def _estimate_cost(budget: int) -> float:
    return budget * TOKENS_PER_PIPELINE_CALL / 1000 * USD_PER_KTOK_IO


def _confirm_cost(budget: int, skip: bool) -> None:
    cost = _estimate_cost(budget)
    print(f"Estimated cost: ${cost:.2f} over {budget} metric calls. "
          f"(rough; real cost depends on LM provider and trace size)")
    if skip:
        return
    ans = input("Continue? [y/N] ").strip().lower()
    if ans not in {"y", "yes"}:
        raise SystemExit("aborted by user")


def _write_diff(baseline: str, candidate: str, label: str, out_dir: Path) -> None:
    diff = difflib.unified_diff(
        baseline.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile=f"baseline/{label}",
        tofile=f"optimized/{label}",
    )
    (out_dir / f"{label}.diff").write_text("".join(diff), encoding="utf-8")


def _write_candidate(candidate: dict[str, str], out_dir: Path) -> None:
    """Write optimized prompts, preserving each baseline frontmatter verbatim.

    Always emits LF line endings — the repo stores agent prompts as LF and CI
    enforces it. Using `write_text` on Windows would rewrite as CRLF and
    pollute git status.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for short in AGENT_NAMES:
        key = short.replace("manim-", "")
        baseline = (BASELINE_DIR / f"{short}.md").read_text(encoding="utf-8")
        fm, _ = split_prompt(baseline)
        _, body = split_prompt(candidate[key])
        merged = join_prompt(fm, body if body else candidate[key])
        (out_dir / f"{short}.md").write_bytes(merged.replace("\r\n", "\n").encode("utf-8"))


def _archive_run(
    run_id: str,
    baseline: dict[str, str],
    best: dict[str, str],
    *,
    config: dict,
    pareto: dict | list[dict] | None,
) -> Path:
    archive = RUNS_DIR / run_id
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if pareto is not None:
        (archive / "pareto.json").write_text(json.dumps(pareto, indent=2), encoding="utf-8")
    for short in AGENT_NAMES:
        key = short.replace("manim-", "")
        _write_diff(baseline[key], best[key], short, archive)
    return archive


def _build_reflection_lm(name: str, claude_model: str):
    """Return either a litellm model string or a Claude CLI callable."""
    if name == "claude":
        return ClaudeCliReflectionLM(model=claude_model)
    return name


def _build_transport(name: str, claude_model: str):
    if name == "claude":
        return ClaudeCliTransport(model=claude_model)
    if name == "litellm":
        return LitellmTransport()
    raise SystemExit(f"unknown transport: {name}")


def _run_gepa(
    adapter,
    seed: dict[str, str],
    trainset: list[dict],
    valset: list[dict],
    budget: int,
    reflection_lm,
    run_dir: Path,
):
    """Lazy import of gepa so the CLI fails loudly only when GEPA is missing.

    Passing `run_dir=` enables GEPA's native per-iteration checkpointing
    (writes `gepa_state.bin` atomically before each iteration). If that file
    already exists in `run_dir`, GEPA auto-resumes from the saved iteration —
    no extra flag needed on our side. `--fresh` wipes the checkpoint upstream
    of this call.
    """
    try:
        import gepa
    except ImportError as exc:
        raise SystemExit(
            "gepa not installed. Run: pip install -e \".[dev]\"\n"
            f"(import error: {exc})"
        )
    _patch_gepa_logger_for_utf8()
    return gepa.optimize(
        seed_candidate=seed,
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        max_metric_calls=budget,
        reflection_lm=reflection_lm,
        display_progress_bar=True,
        run_dir=str(run_dir),
        cache_evaluation=True,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--trainset", type=Path, default=REPO_ROOT / "tests/gepa/trainset.yaml")
    p.add_argument("--valset", type=Path, default=REPO_ROOT / "tests/gepa/valset.yaml")
    p.add_argument("--budget", type=int, default=150, help="GEPA max_metric_calls")
    p.add_argument("--reflection-lm", default=DEFAULT_REFLECTION_LM,
                   help="litellm model string OR the literal 'claude' to use Claude CLI subprocess.")
    p.add_argument("--transport", default="litellm", choices=["litellm", "claude"],
                   help="How to execute candidate pipelines. 'claude' uses the local CLI (no API key).")
    p.add_argument("--claude-model", default="claude-sonnet-4-6",
                   help="Claude model ID used by --transport claude AND --reflection-lm claude. "
                        "Default: claude-sonnet-4-6 (balanced, accessible on standard plans). "
                        "Use claude-opus-4-7 if you have a flagship plan and want the best reflection quality.")
    p.add_argument("--allow-claude-reflection", action="store_true",
                   help="Bypass the Claude-family reflection-LM guard. Required when --reflection-lm starts with anthropic/claude.")
    p.add_argument("--output", type=Path, default=AGENTS_DIR,
                   help="Where to write the 3 optimized .md files (default: agents/)")
    p.add_argument("--user", action="store_true",
                   help="Write to per-user override dir instead of plugin agents/")
    p.add_argument("--minibatch", type=int, default=3, help="(documented; passed via env to gepa)")
    p.add_argument("--reruns", type=int, default=1, help="Per-candidate reruns for variance")
    p.add_argument("--quality", choices=["low", "medium", "high"], default="low")
    p.add_argument("--yes", action="store_true", help="Skip cost confirmation prompt")
    p.add_argument("--run-id", default=None,
                   help="Default = ISO timestamp. Pass an existing run-id to resume "
                        "from its last checkpoint (auto-detected).")
    p.add_argument("--fresh", action="store_true",
                   help="Delete any existing gepa_state.bin in the run-dir before "
                        "starting. Use this if you want to start the same --run-id over.")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan and confirm but skip the GEPA call (sanity check)")
    args = p.parse_args(argv)

    run_id = args.run_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_DIR / run_id
    output_dir = ensure_override_dir() if args.user else args.output

    checkpoint = run_dir / "gepa_state.bin"
    if args.fresh and checkpoint.exists():
        checkpoint.unlink()
        print(f"[fresh] removed {checkpoint}")
    resume_mode = checkpoint.exists()

    trainset = _load_yaml_list(args.trainset)
    valset = _load_yaml_list(args.valset)
    baseline = _load_baseline_candidate()

    print(f"run_id           : {run_id}")
    print(f"run dir          : {run_dir}")
    print(f"trainset entries : {len(trainset)}")
    print(f"valset entries   : {len(valset)}")
    print(f"reflection_lm    : {args.reflection_lm}")
    print(f"output dir       : {output_dir}")
    print(f"checkpoint       : {'RESUME from ' + str(checkpoint) if resume_mode else 'fresh run'}")

    _confirm_cost(args.budget, args.yes or args.dry_run)

    transport = _build_transport(args.transport, args.claude_model)
    allow_claude_refl = args.allow_claude_reflection or args.reflection_lm == "claude"
    adapter = ManimSkillAdapter(
        valset=valset, run_id=run_id,
        reflection_lm=args.reflection_lm,
        reruns=args.reruns, quality=args.quality,
        transport=transport,
        allow_claude_reflection=allow_claude_refl,
    )
    reflection_lm = _build_reflection_lm(args.reflection_lm, args.claude_model)

    print(f"transport       : {args.transport}{' (' + args.claude_model + ')' if args.transport == 'claude' else ''}")
    if args.reflection_lm == "claude":
        print(f"reflection model : {args.claude_model}")

    if args.dry_run:
        print("[dry-run] skipping gepa.optimize; writing baseline as 'best'")
        best = baseline
        pareto = None
    else:
        run_dir.mkdir(parents=True, exist_ok=True)
        result = _run_gepa(
            adapter, baseline, trainset, valset,
            args.budget, reflection_lm, run_dir,
        )
        best = getattr(result, "best_candidate", result)
        # GEPAResult has no `pareto_frontier` attr — surface the real
        # per-candidate aggregate scores so pareto.json stays meaningful.
        pareto = {
            "val_aggregate_subscores": getattr(result, "val_aggregate_subscores", None),
            "best_idx": getattr(result, "best_idx", None),
            "total_metric_calls": getattr(result, "total_metric_calls", None),
            "num_candidates": getattr(result, "num_candidates", None),
        }

    _write_candidate(best, output_dir)
    archive = _archive_run(
        run_id, baseline, best,
        config={
            "trainset": str(args.trainset),
            "valset": str(args.valset),
            "budget": args.budget,
            "reflection_lm": args.reflection_lm,
            "quality": args.quality,
            "reruns": args.reruns,
            "output_dir": str(output_dir),
            "estimated_cost_usd": round(_estimate_cost(args.budget), 2),
        },
        pareto=pareto,
    )
    print(f"Wrote optimized prompts to: {output_dir}")
    print(f"Run archive             : {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
