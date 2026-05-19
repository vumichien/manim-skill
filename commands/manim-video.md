---
description: Generate a Manim animation from an idea, paper, or math topic via a 4-role agent pipeline.
argument-hint: --idea \"<topic>\" | --paper <id-or-url> | --math \"<topic>\" [--voice gtts|openai|elevenlabs] [--no-voice] [--no-chrome] [--transition-s 0.7] [--quality low|medium|high|4k] [--storyboard-only] [--out <dir>] [--optimize <corpus.yaml>]
---

# /manim-video

Turn ideas, papers, and math topics into Manim videos.

## One of these is required

- `--idea "<topic>"` — pure topic; the pipeline invents scope and structure.
- `--paper <arxiv-id|url|path>` — auto-detects arXiv id, PDF (local or URL), or HTML page.
- `--math "<topic>"` — math-explainer specialization; uses MathTex when LaTeX is available, else falls back to Text.

## Optional

- `--voice gtts|openai|elevenlabs` — narration via manim-voiceover. **Default: `gtts`** (since schema 0.2.0).
  - `gtts` is keyless. `openai` needs `OPENAI_API_KEY`. `elevenlabs` needs `ELEVENLABS_API_KEY`.
  - On voice-related failure (network / missing key), the pipeline downgrades all remaining scenes to caption-only.
- `--no-voice` — opt out of narration. Captions still render via the chrome track. Mutually exclusive with `--voice`.
- `--no-chrome` — disable header bar + title cards. Captions still render. Escape hatch for advanced users.
- `--transition-s <float>` — override scene cross-fade duration. Range 0.3–1.5; default 0.7. Stored as `meta.transition_s` in the storyboard.
- `--quality low|medium|high|4k` — render quality; default `high` (1920×1080 @ 60fps).
- `--storyboard-only` — stop after producing storyboard.yaml; skip rendering.
- `--out <dir>` — override output directory; default `out/<run-id>/`.
- `--optimize <corpus.yaml>` — **power-user** mode. Delegates to
  `scripts/optimize-prompts.py --user --trainset <corpus.yaml>` so GEPA can
  tune the 3 agent prompts against your own topic corpus. Results write to a
  per-user override dir (`%USERPROFILE%\.manim-skill\agents-override\` on
  Windows, `$XDG_CONFIG_HOME/manim-skill/agents-override/` on POSIX) and are
  picked up on the next `/manim-video` run. Costs $5-20 per full run — see
  `docs/gepa-optimization.md`. Requires `pip install -e ".[dev]"`.

### Voice resolution precedence

```
--no-voice       → null (no audio, captions only)
--voice <p>      → <p>
default          → gtts
```

`--no-voice` and `--voice` cannot be combined.

## Activation

This command activates the **manim-video** skill, which orchestrates a 4-role pipeline (researcher + planner + implementer + main). See `skills/manim-video/SKILL.md` for the full flow.

## Examples

```
/manim-video --idea "Why is the sky blue?"
/manim-video --idea "Why is the sky blue?" --no-voice
/manim-video --paper 1706.03762 --voice openai --quality high
/manim-video --math "Pythagorean theorem" --transition-s 1.0
/manim-video --paper ./research.pdf --storyboard-only
/manim-video --idea "Bayes' theorem" --no-chrome --no-voice
```

See [`docs/storyboard-migration-0.2.0.md`](../docs/storyboard-migration-0.2.0.md) for the schema 0.2.0 contract.
