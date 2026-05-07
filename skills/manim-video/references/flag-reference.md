# Flag Reference

Long-form semantics for `/manim-video` flags.

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

**Example:** `/manim-video --paper 1706.03762 --voice gtts`
**Skill behavior:** Step 2 (ingest) writes `out/<run>/source.md`; researcher reads from there.

### `--math "<topic>"`

Math-explainer specialization. Same flow as `--idea` but the planner is biased toward `MathTex`, `Axes`, `NumberPlane`, and `Transform` patterns. Pre-checks `xelatex --version`; if absent, downgrades MathTex hints to Text.

**Example:** `/manim-video --math "Pythagorean theorem"`

## Optional flags

### `--voice [gtts|openai|elevenlabs]`

Enables narration via `manim-voiceover`. Implementer wraps each scene's `self.play(...)` calls in a `with self.voiceover(text=...)` context manager and uses `tracker.duration` for `run_time`.

| Provider | Cost | Setup |
|---|---|---|
| `gtts` (default if `--voice` is given without value) | free | none |
| `openai` | paid | `OPENAI_API_KEY` env var |
| `elevenlabs` | paid | `ELEVENLABS_API_KEY` env var |

If voice is set but the matching scene field `voiceover_text` is empty/null, the implementer emits a silent scene (no `voiceover` block).

See `voiceover-setup.md` for env-var details.

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

Output dir contains: `outline.md`, `storyboard.draft.yaml`, `storyboard.yaml`, `summary.md`. No `scenes/` or `video.mp4`.

### `--out <dir>`

Override the default `out/<run-id>/`. Skill still creates a `<run-id>` subdir inside it for namespacing. Useful when running many renders and you want them grouped (e.g. `--out renders/2026-q2/`).

## Combining flags

Examples seen in CI:

```bash
/manim-video --idea "Bayes' theorem" --voice gtts --quality medium
/manim-video --paper 1706.03762 --voice openai --quality high
/manim-video --math "Eigenvalues" --storyboard-only
/manim-video --paper https://en.wikipedia.org/wiki/Pythagorean_theorem --quality low
```

## Errors and exit codes

| Situation | Skill response |
|---|---|
| No mode flag | Refuse, list flags |
| Two mode flags | Refuse, ask user to pick one |
| `--voice openai` without `OPENAI_API_KEY` | Warn, fall back to gtts |
| `--math` without LaTeX | Warn, downgrade MathTex → Text in storyboard |
| Ingest fails | Stop after T0; summary.md flags failure |
| Storyboard validation fails twice | Stop before render; summary.md flags failure |
| Render fails after retry budget | Keep successful scenes; summary.md flags incomplete |
