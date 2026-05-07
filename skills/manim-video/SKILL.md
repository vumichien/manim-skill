---
name: manim-video
description: Generate Manim animations from ideas, research papers, or math topics. Use when user asks to "make a video about X", "animate X", "explain X with Manim", or invokes /manim-video. Orchestrates a 4-role pipeline (researcher + planner + implementer + main) to produce out/<run-id>/video.mp4 plus storyboard, scenes, and narration script.
license: Apache-2.0
metadata:
  author: vumichien
  version: "0.1.0"
  homepage: https://github.com/vumichien/manim-skill
---

# manim-video

Turn ideas, papers, and math topics into rendered Manim animations.

## When to use

Activate this skill whenever the user wants:
- A short explanatory video for a concept ("explain Fourier transforms", "animate Pythagoras")
- A research paper visualized ("turn this arXiv paper into a 5-min video")
- A math derivation animated step by step
- Any invocation of `/manim-video --idea | --paper | --math`

Do **not** activate for:
- Static images or single-frame plots — use matplotlib / `/ck:ai-multimodal` instead
- Slideshow presentations — use `manim-slides` or `/ck:remotion`
- Generic web animation — use `/ck:remotion` or shaders

## Inputs

| Flag | Required | Notes |
|---|---|---|
| `--idea "<topic>"` | one of these three | Pure topic; pipeline invents scope. |
| `--paper <id\|url\|path>` | one of these three | arXiv id, PDF (local/URL), or HTML page. |
| `--math "<topic>"` | one of these three | Math specialization; prefers MathTex when LaTeX available. |
| `--voice [gtts\|openai\|elevenlabs]` | optional | Default: no voice. `gtts` is keyless. |
| `--quality low\|medium\|high\|4k` | optional | Default `high` (1080p60). |
| `--storyboard-only` | optional | Stop after T1; skip rendering. |
| `--out <dir>` | optional | Default `out/<run-id>/`. |

Run-id format: `<YYMMDD-HHMM>-<slug>` (slug derived from topic, ≤40 chars).

## Pipeline

```
T0 main → spawn manim-researcher  (reads source.md if --paper)  → outline.md
       || spawn manim-planner skeleton                          → storyboard.draft.yaml
T1 main → spawn manim-planner final (reads outline + draft)     → storyboard.yaml
T2 main → spawn manim-implementer (reads storyboard, retries)   → scenes/scene_*.py + video.mp4
T3 main → write summary.md
```

### Step-by-step

1. **Parse flags.** Validate exactly one of `--idea/--paper/--math`. Derive `run_id` and `out_dir`. Set `voice = flag_value or null`. Set `quality = flag_value or "high"`. Read `manim_version` from installed `manim` (or fall back to `0.20.x`).

2. **Ingest (only if `--paper`).** Run:
   ```bash
   python scripts/ingest-router.py "<source>" --out <out_dir>
   ```
   Produces `<out_dir>/source.md` + `<out_dir>/source.meta.json`. If exit non-zero: stop, write summary.md with error.

3. **T0 — spawn two agents in parallel.**

   Read `agents/manim-researcher.md` and `agents/manim-planner.md`. Spawn both via the `Task` tool **in a single message** so they run concurrently:

   - Task A: subagent_type=`general-purpose`, prompt = `<contents of agents/manim-researcher.md>` + run-specific args:
     ```
     RUN ARGS:
       run_id: <run_id>
       out_dir: <out_dir>
       source: idea|math|paper:<ref>
       topic: "<topic>"
       source_md_path: <out_dir>/source.md   # only if --paper
     OUTPUT: write <out_dir>/outline.md (≤300 lines, sections: tldr, key_concepts, derivations_or_proofs, visual_metaphors, narrative_arc)
     ```

   - Task B: subagent_type=`general-purpose`, prompt = `<contents of agents/manim-planner.md>` + skeleton-mode args:
     ```
     RUN ARGS:
       mode: skeleton
       run_id: <run_id>
       out_dir: <out_dir>
       topic: "<topic>"
       voice: <voice or null>
       quality: <quality>
     OUTPUT: write <out_dir>/storyboard.draft.yaml (scene IDs + beats + durations only; mobjects/animations as TODO).
     ```

4. **T1 — final storyboard.** After T0 returns, spawn:
   - subagent_type=`general-purpose`, prompt = `<contents of agents/manim-planner.md>` + final-mode args:
     ```
     RUN ARGS:
       mode: final
       run_id: <run_id>
       out_dir: <out_dir>
       outline_path: <out_dir>/outline.md
       draft_path:   <out_dir>/storyboard.draft.yaml
     OUTPUT: write <out_dir>/storyboard.yaml — fully populated mobjects/animations per schemas/storyboard.schema.json.
     ```

   Validate the result:
   ```bash
   python scripts/validate-storyboard.py <out_dir>/storyboard.yaml
   ```
   If exit non-zero: re-spawn the planner once with the validator's stderr appended to the prompt as `VALIDATION_ERRORS:`. After two failures, escalate to summary.md.

5. **`--storyboard-only` short-circuit.** If flag set, jump to step 7.

6. **T2 — implementer.** Spawn:
   - subagent_type=`general-purpose`, prompt = `<contents of agents/manim-implementer.md>` + args:
     ```
     RUN ARGS:
       run_id: <run_id>
       out_dir: <out_dir>
       storyboard_path: <out_dir>/storyboard.yaml
       quality: <quality>
       voice: <voice or null>
       retry_budget: 5
     OUTPUT: write <out_dir>/scenes/scene_NN.py for each scene; render via scripts/render.py; concatenate into <out_dir>/video.mp4. Honor retry budget per scene.
     ```

   Implementer writes a `<out_dir>/render.log` with per-scene render JSON and timings.

7. **T3 — summary.** Write `<out_dir>/summary.md` with:
   - Run id, command-line args, total duration
   - Paths: source.md, outline.md, storyboard.yaml, scenes/, video.mp4 (if rendered)
   - Render outcomes (per scene: ok / error_class / render_time_s)
   - Next steps if errors occurred

## Outputs

```
out/<run-id>/
├── source.md         # only if --paper (frontmatter + extracted markdown)
├── source.meta.json  # only if --paper
├── outline.md        # researcher: tldr + key concepts + visual metaphors + narrative arc
├── storyboard.draft.yaml  # planner skeleton
├── storyboard.yaml   # planner final (validated)
├── scenes/
│   └── scene_NN.py   # implementer-emitted Manim scenes
├── manim_media/      # raw Manim render artifacts
├── video.mp4         # final concatenated render (or per-scene mp4s if no concat)
├── render.log        # per-scene render JSON
└── summary.md
```

## Error handling

- **Ingest fails** → stop after step 2; summary.md notes the URL/PDF that failed.
- **Storyboard invalid twice** → escalate to user; do not start rendering.
- **Render fails after retry budget exhausted** → implementer keeps successful scenes, logs failed ones in render.log; main concatenates only successful scenes; summary.md flags incomplete render.
- **LaTeX missing + --math used** → main pre-checks `xelatex --version`. If absent: warn user, downgrade MathTex hints to Text in the storyboard via planner second-pass.

## References

Lazy-load these only when needed:

- [`references/manim-api-cheatsheet.md`](references/manim-api-cheatsheet.md) — Mobject + animation reference
- [`references/storyboard-schema.md`](references/storyboard-schema.md) — Storyboard YAML format
- [`references/flag-reference.md`](references/flag-reference.md) — Long-form flag semantics
- [`references/render-runner-contract.md`](references/render-runner-contract.md) — `scripts/render.py` JSON contract
- [`references/voiceover-setup.md`](references/voiceover-setup.md) — TTS provider env vars

Agent prompts live in `agents/`:

- [`agents/manim-researcher.md`](../../agents/manim-researcher.md)
- [`agents/manim-planner.md`](../../agents/manim-planner.md)
- [`agents/manim-implementer.md`](../../agents/manim-implementer.md)

## Pre-flight

Before T0, verify the venv is ready:
```bash
python scripts/check-env.py
```
If exit non-zero: instruct user to run `pwsh scripts/install.ps1` (Windows) or `bash scripts/install.sh` (Linux/macOS), then retry.
