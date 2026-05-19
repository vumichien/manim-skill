# Flag Reference

Long-form semantics for `/manim-video` flags (schema 0.2.0).

## Mode flags (one required)

### `--idea "<topic>"`

Pure topic input. The pipeline invents the entire scope: what to cover, how many scenes, what visual metaphors fit. Best for short conceptual videos.

**Example:** `/manim-video --idea "Why is the sky blue?"`
**Skill behavior:** No ingest step. Researcher writes outline directly from the topic string.

### `--paper <id|url|path>`

Auto-detects (priority order):

1. arXiv URL (`arxiv.org/abs/...` or `arxiv.org/pdf/...`) → arxiv ingestor (metadata-rich)
2. arXiv id pattern (`1706.03762`, `hep-ex/0307015`, `arxiv:1234.56789v2`) → arxiv ingestor
3. `.pdf` suffix (local path or remote URL) → pdf ingestor
4. http(s) URL otherwise → html ingestor (trafilatura, fallback readability-lxml)

Multi-source (`--paper id1 --paper id2`) is **not** supported in v0.1; use a single source.

**Example:** `/manim-video --paper 1706.03762`
**Skill behavior:** Step 2 (ingest) writes `out/<run>/source.md`; researcher reads from there.

### `--math "<topic>"`

Math-explainer specialization. Same flow as `--idea` but the planner is biased toward `MathTex`, `Axes`, `NumberPlane`, and `Transform` patterns. Pre-checks `xelatex --version`; if absent, downgrades MathTex hints to Text.

**Example:** `/manim-video --math "Pythagorean theorem"`

## Voice flags

### `--voice gtts|openai|elevenlabs`

Enables narration via `manim-voiceover`. **Default since 0.2.0: `gtts`.** When omitted entirely, the pipeline still resolves to `gtts` (was `null` in 0.1.x — a friendly breaking change called out in release notes).

| Provider | Cost | Setup |
|---|---|---|
| `gtts` (default) | free | none |
| `openai` | paid | `OPENAI_API_KEY` env var |
| `elevenlabs` | paid | `ELEVENLABS_API_KEY` env var |

Voice fallback policy: on first network/import failure, the implementer retries once. On second failure, all remaining scenes downgrade to caption-only — captions still render, just without TTS audio. Logged in error.md.

See `voiceover-setup.md` for env-var details.

### `--no-voice`

Opt out of narration entirely. Captions still render via the chrome track using `voiceover_text` from the storyboard. Mutually exclusive with `--voice`.

**Example:** `/manim-video --idea "Bayes" --no-voice`

Equivalent to the old `--voice null` from 0.1.x.

## Chrome flags

### `--no-chrome`

Disable header bar + per-scene title cards. Captions still render. Use this when:

- The body mobject geometry would otherwise collide with chrome
- You want a "bare scenes" deliverable for a third-party editor
- Producing assets to overlay in Premiere / DaVinci

The flag toggles `meta.show_progress: false` AND every scene's `show_title_card: false`.

**Example:** `/manim-video --idea "wave equation" --no-chrome`

### `--transition-s <float>`

Override the default cross-fade duration between scenes. Range 0.3–1.5 seconds. Stored as `meta.transition_s` in the storyboard and used by `scripts/concat-xfade.py` at concat time.

| Value | Feel |
|---|---|
| 0.3 | Snappy, almost a hard cut |
| 0.7 (default) | Standard educational |
| 1.0 | Cinematic |
| 1.5 | Slow / dramatic |

Out-of-range values are clamped with a warning.

**Example:** `/manim-video --math "Fourier" --transition-s 1.0`

## Quality + storage flags

### `--quality low|medium|high|4k`

Maps to Manim CLI quality flags:

| Value | Manim flag | Resolution | FPS | Render speed |
|---|---|---|---|---|
| `low` | `-ql` | 854×480 | 15 | fastest (dev) |
| `medium` | `-qm` | 1280×720 | 30 | quick preview |
| `high` (default) | `-qh` | 1920×1080 | 60 | publish |
| `4k` | `-qk` | 3840×2160 | 60 | hero shot |

### `--storyboard-only`

Stops after T1 (validated `storyboard.yaml`). Skips implementer + render. Useful for:
- Reviewing pacing before committing to a render
- Iterating on outline + storyboard with the user
- Producing storyboards for human-rendered videos

Output dir contains: `outline.md`, `storyboard.draft.yaml`, `storyboard.yaml`, `summary.md`. No `scenes/`, `video.mp4`, or `captions.srt`.

### `--out <dir>`

Override the default `out/<run-id>/`. Skill still creates a `<run-id>` subdir inside it for namespacing. Useful when running many renders and you want them grouped (e.g. `--out renders/2026-q2/`).

## Combining flags

```bash
/manim-video --idea "Bayes' theorem" --voice gtts --quality medium
/manim-video --paper 1706.03762 --voice openai --quality high
/manim-video --math "Eigenvalues" --storyboard-only
/manim-video --paper https://en.wikipedia.org/wiki/Pythagorean_theorem --quality low
/manim-video --idea "wave equation" --no-voice --no-chrome
/manim-video --math "Fourier" --transition-s 1.0
```

## Errors and exit codes

| Situation | Skill response |
|---|---|
| No mode flag | Refuse, list flags |
| Two mode flags | Refuse, ask user to pick one |
| Both `--voice` and `--no-voice` | Refuse, ask user to pick one |
| `--voice openai` without `OPENAI_API_KEY` | Warn, fall back to gtts |
| Voice fallback at runtime | First failure: retry. Second failure: downgrade all remaining scenes to caption-only |
| `--transition-s 2.0` | Warn, clamp to 1.5 |
| `--math` without LaTeX | Warn, downgrade MathTex → Text in storyboard |
| Ingest fails | Stop after T0; summary.md flags failure |
| Storyboard validation fails twice | Stop before render; summary.md flags failure |
| Render fails after retry budget | Keep successful scenes; summary.md flags incomplete |
| `xfade` filter unavailable | concat-xfade falls back to plain concat (hard cuts); warn in summary.md |

## `--optimize <corpus.yaml>` (power-user, since 0.3.0)

Off the rendering hot-path. The flag delegates to
`scripts/optimize-prompts.py` and:

- Reads `<corpus.yaml>` as the GEPA trainset (same shape as
  `tests/gepa/trainset.yaml`).
- Re-runs GEPA on top of `agents/_baseline/` and writes optimized prompts to
  the per-user override dir (see `scripts/agents_override_path.py`).
- Skips rendering — this run produces prompts, not videos. Run the slash
  command again (without `--optimize`) to use the optimized prompts.

Requires `pip install -e ".[dev]"` and an OpenAI-family reflection-LM key
(default `OPENAI_API_KEY`). See `docs/gepa-optimization.md` for cost and
review workflow.
