# Reproducing & extending the GEPA optimization

This is the developer-facing step-by-step for running the GEPA prompt
optimizer against the `manim-skill` agent prompts. It assumes a fresh
checkout.

`manim-skill` ships **baseline agent prompts** under `agents/` and the
**frozen pre-GEPA originals** under `agents/_baseline/`. Optimization
mutates the former in place, seeded by the latter. The metric is defined
in `scripts/gepa_metrics.py::composite_score` (weights table below).

## TL;DR

```powershell
# 1. one-time setup
git clone https://github.com/<owner>/manim-skill.git
cd manim-skill
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"      # gets manim, gepa, litellm, pytest, ...
claude --version              # required for --transport claude (the default recipe)

# 2. tests pass on a fresh clone
.\.venv\Scripts\python.exe -m pytest tests\ -q

# 3. smoke a 15-minute run (claude CLI, Sonnet 4.6, no API key)
python scripts/optimize-prompts.py `
    --transport claude --reflection-lm claude `
    --claude-model claude-sonnet-4-6 `
    --budget 3 --reruns 1 --quality low --yes `
    --run-id my-smoke

# 4. inspect the result
Get-Item plans\gepa-runs\my-smoke\manim-*.diff | Format-Table Name, Length
```

If step 4 shows three non-zero `.diff` files you have a working run.
Move on to a real budget (~20) and review the diffs.

## Prerequisites

| Requirement | Why | Notes |
|---|---|---|
| Python 3.11+ | matches `pyproject.toml` | 3.11 is what we test against |
| `pip install -e ".[dev]"` | brings in `gepa>=0.1.1`, `litellm`, pytest, manim | the runtime install does **not** include GEPA — it lives in the `dev` extras only |
| `claude` CLI on `PATH` (Claude Code) | default transport + reflection LM | login once via `claude login`; the GEPA scripts shell out to your existing session |
| FFmpeg + Cairo (for Manim render) | the regression metric re-renders sample scenes | install per the [Manim docs](https://docs.manim.community/en/stable/installation.html) |
| Optional: `OPENAI_API_KEY` / litellm provider key | only if you skip `--transport claude` and want litellm-driven runs | set in `.env` — never commit |

Verify the install end-to-end:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\gepa\ -q
# expect: ~50 passed
```

## What gets optimized

GEPA mutates **three files in place** under `agents/`:

```
agents/manim-researcher.md
agents/manim-planner.md
agents/manim-implementer.md
```

The frozen pre-GEPA originals live in `agents/_baseline/` — the script
seeds optimization from those, and that directory doubles as the
rollback source.

Each candidate is scored by `scripts/gepa_metrics.composite_score`:

| Axis | Weight | What it measures |
|---|---|---|
| `storyboard_valid` | 0.4 | Storyboard YAML validates against `schemas/storyboard.schema.json` |
| `render_success` | 0.3 | All emitted scene files render to MP4 |
| `mathtex_nonempty` | 0.2 | No frame shows a suspected-empty MathTex (heuristic) |
| `regression_ok` | 0.1 | `samples/01-06` still render after running this candidate's implementer |

To rebalance, edit `composite_score` (keep weights summing to 1.0) and
update the table above.

## Trainset & valset

| File | Purpose | Mutable? |
|---|---|---|
| `tests/gepa/trainset.yaml` | 30 hand-curated topics the optimizer iterates over | yes — extend or replace for a domain-specific run |
| `tests/gepa/valset.yaml` | 6 canonical samples used for unbiased scoring | **no — hashed in CI**; see `.valset.sha256` |
| `tests/gepa/.valset.sha256` | enforces valset immutability | regenerate only when the valset legitimately changes; CI requires a `samples-valset-update` PR label |

To run against your own corpus, write a YAML file in the same shape as
`trainset.yaml` and pass `--trainset path/to/yours.yaml`. Each entry is
a single topic dict — see `tests/gepa/trainset.yaml` for examples.

## The minimum viable run

```powershell
python scripts/optimize-prompts.py `
    --transport claude `
    --reflection-lm claude `
    --claude-model claude-sonnet-4-6 `
    --budget 3 --reruns 1 --quality low --yes `
    --run-id my-smoke
```

| Flag | Effect |
|---|---|
| `--transport claude` | spawn `claude --print` for each candidate-pipeline call instead of `litellm` |
| `--reflection-lm claude` | reuse the Claude CLI for GEPA's reflection step (no API key required) |
| `--claude-model claude-sonnet-4-6` | balanced default: works on standard plans, faster than Opus |
| `--budget 3` | total rollouts across all iterations |
| `--reruns 1` | per-candidate reruns for variance (raise for noisy metrics) |
| `--quality low` | manim render quality — `low` is ~10× faster than `high` |
| `--yes` | skip the cost confirmation prompt |
| `--run-id my-smoke` | name the archive dir under `plans/gepa-runs/` |

The launch will:

1. Load trainset + valset.
2. Print a cost estimate (rough; the Claude CLI consumes your plan quota).
3. Open a `run_dir = plans/gepa-runs/my-smoke/`.
4. Start the GEPA loop. After every iteration it writes
   `gepa_state.bin` — that is your resume point.
5. On exit (clean or interrupt), write `manim-*.diff` files comparing
   baseline → best candidate, plus `config.json` and `pareto.json`.

Watch for these markers in stdout:

```
Iteration 0: Base program full valset score: 0.X over Y / Y examples
Iteration N: Selected program K score: 0.X
Iteration N: Proposed new text for <component>      <- the optimizer is working
Iteration N: New program is on the linear pareto front. Adding it.
```

If you only ever see `Iteration N: Reflective mutation did not propose a
new candidate`, jump to [Troubleshooting](#troubleshooting).

## Running for real (budget=20+, ~75 min on Sonnet)

```powershell
python scripts/optimize-prompts.py `
    --transport claude --reflection-lm claude `
    --claude-model claude-sonnet-4-6 `
    --budget 20 --reruns 1 --quality low --yes `
    --run-id 260520-real
```

Long runs in the background:

```powershell
$log = "plans\gepa-runs\launch.log"
Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "scripts/optimize-prompts.py --transport claude --reflection-lm claude --claude-model claude-sonnet-4-6 --budget 20 --reruns 1 --quality low --yes --run-id 260520-real" `
    -RedirectStandardOutput $log -RedirectStandardError $log -NoNewWindow
Get-Content $log -Wait   # Ctrl+C only stops the tail; the run keeps going
```

Wall-time observed: ~50–80 minutes for `budget=20` on Sonnet 4.6,
single-threaded.

## Pausing and resuming

GEPA writes a per-iteration checkpoint before every iteration starts. To
pause: `Ctrl+C` the process, or `taskkill /PID <pid> /T /F`. To resume,
**re-invoke the exact same command with the same `--run-id`** — the
checkpoint is auto-detected:

```
checkpoint       : RESUME from C:\...\plans\gepa-runs\<run-id>\gepa_state.bin
```

Notes:

- `--budget 20` on resume means **20 total** rollouts across both
  sessions, not "20 more" — GEPA's counter is restored from the
  checkpoint.
- The `evaluation_cache` is preserved, so identical candidate+topic
  pairs are not re-evaluated.
- `--fresh` deletes `gepa_state.bin` for that `--run-id` before
  starting. Use this if you want to start the same run-id over.

## Reviewing & accepting a run

```powershell
$id = "260520-real"
ls plans\gepa-runs\$id\

# Did the optimizer actually improve anything?
Get-Item plans\gepa-runs\$id\manim-*.diff | Format-Table Name, Length

# Eyeball the changes
Get-Content plans\gepa-runs\$id\manim-researcher.diff
```

Acceptance gate:

1. Every diff must preserve YAML frontmatter exactly (the adapter
   enforces, but double-check).
2. Tool lists in the frontmatter must be untouched.
3. Render `samples/01-06` against the optimized prompts:
   ```powershell
   pwsh samples\build-samples.ps1
   ```
   Each must produce a valid `out.mp4` with no blank MathTex frames.
4. Full unit suite green:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests\ -q
   ```

If 1–4 hold, commit the new agent files and the run archive metadata
(`config.json` + `pareto.json` only; the binary `gepa_state.bin` and
the `candidates/` work-dirs stay gitignored).

## Rollback

```powershell
copy agents\_baseline\manim-researcher.md  agents\manim-researcher.md
copy agents\_baseline\manim-planner.md     agents\manim-planner.md
copy agents\_baseline\manim-implementer.md agents\manim-implementer.md
```

## Troubleshooting

### All diffs are zero bytes

The optimizer ran the metric calls but never accepted a candidate
mutation. Two causes worth checking first, in order:

1. **`Iteration N: Reflective mutation did not propose a new candidate`** for every iteration.

   Open the launch log (or redirected stdout) and look for the
   underlying exception. Common ones below.

2. **`claude --print exit 1: stderr=''`** — Windows arg-length crash.
   Reflection prompts can exceed 32K chars; `CreateProcess` silently
   rejects them. The fix in `scripts/gepa_adapter.py::ClaudeCliReflectionLM.__call__`
   and `scripts/gepa_invoke_agents.py::_claude_print` pipes the prompt via
   stdin instead of argv. Verify with:
   ```
   .venv\Scripts\python.exe -m pytest tests\gepa\test_claude_stdin.py -v
   ```
   All six tests should pass. A failure here means a regression — both
   call sites must use `input=` (stdin), not append the prompt to `cmd`.

3. **`UnicodeEncodeError: 'cp932' codec can't encode character`** — only
   bites on Japanese (or other non-UTF-8) Windows locales. The fix in
   `scripts/optimize-prompts.py` reconfigures stdout/stderr to UTF-8 and
   monkey-patches `gepa.logging.logger.Logger.__init__` to open its files
   with explicit `encoding="utf-8"`. If you ever lose this guard,
   workaround: set `$env:PYTHONUTF8 = "1"` before launching.

### `claude --print` works manually but exits 1 from the script

Could be:

- Auth expired — run `claude login`.
- Plan quota exhausted — check `claude /usage` (interactive shell).
- The CLI was upgraded and broke `--print` semantics — pin a known-good
  version in CI.

### Reflection LM produces text but GEPA rejects every candidate

Look for `Iteration N: New program scored worse than parent`. The
proposer is generating mutations the metric scores below baseline. Causes:

- Trainset is too narrow (every topic forces the same prompt structure).
- The metric weights overemphasize one axis (see weights table above).
- Reflection LM is the same family as the candidate LM — bias. Use a
  cross-family reflection LM (default `openai/gpt-4.1-mini`) for the
  unbiased baseline.

### Pipeline crashes mid-iteration

Read `plans/gepa-runs/<run-id>/candidates/<NNN>/` for the working dir
of the candidate that failed. Common findings:

- `storyboard.yaml` is empty → transport produced nothing parseable.
  Re-running often resolves transient API hiccups; persistent issue
  points to a prompt regression in `agents/_baseline/manim-researcher.md`.
- `scene_NN.py` import errors → implementer hallucinating a new Manim
  API. Score drops, optimizer learns to avoid it.

### Run completed but didn't write a `gepa_state.bin`

GEPA writes the checkpoint at the **top of each iteration**, so if the
seed evaluation crashes (iteration 0), no state is persisted. Look
above for the actual exception trace; usually a misconfigured transport
or missing baseline file.

## Extending the optimizer

| You want to… | Edit |
|---|---|
| Add a new metric axis | `scripts/gepa_metrics.py::composite_score` — keep weights summing to 1.0 |
| Swap reflection LM provider | `--reflection-lm openai/gpt-4o`, or any litellm string; the `--allow-claude-reflection` flag bypasses the same-family guard if you really want claude→claude |
| Tune for a new domain | Add 20–50 topics to a new `tests/gepa/<domain>-trainset.yaml`, pass `--trainset` |
| Cap LM cost | Lower `--budget` (linear) and/or `--reruns` (default 1, raises noise resistance) |
| Use a per-user override dir (don't touch repo `agents/`) | `--user` — writes to `%USERPROFILE%\.manim-skill\agents-override\` (Windows) or `$XDG_CONFIG_HOME/manim-skill/agents-override/` (POSIX) |

## Reading list

- [GEPA paper (arXiv:2507.19457)](https://arxiv.org/abs/2507.19457) — the algorithm.
- `tests/gepa/README.md` — what each test in the suite covers.
- `scripts/gepa_adapter.py`, `scripts/gepa_invoke_agents.py`,
  `scripts/gepa_pipeline_runner.py`, `scripts/gepa_metrics.py`,
  `scripts/optimize-prompts.py` — annotated source; start at
  `optimize-prompts.py::main` and follow imports.

## Reporting issues

If you hit a failure not covered above, before opening an issue please
collect:

1. `git rev-parse HEAD`
2. `python -V`, `claude --version`, `pip show gepa | findstr Version`
3. Full launch log
4. `plans/gepa-runs/<run-id>/run_log_stderr.txt`
5. The `--run-id` and exact command invocation
6. `.\.venv\Scripts\python.exe -m pytest tests\gepa\ -v` output

Attach those to an issue rather than re-running blind.
