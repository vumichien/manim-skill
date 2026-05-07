---
description: Generate a Manim animation from an idea, paper, or math topic via a 4-role agent pipeline.
argument-hint: --idea \"<topic>\" | --paper <id-or-url> | --math \"<topic>\" [--voice gtts|openai|elevenlabs] [--quality low|medium|high|4k] [--storyboard-only] [--out <dir>]
---

# /manim-video

Turn ideas, papers, and math topics into Manim videos.

## One of these is required

- `--idea "<topic>"` — pure topic; the pipeline invents scope and structure.
- `--paper <arxiv-id|url|path>` — auto-detects arXiv id, PDF (local or URL), or HTML page.
- `--math "<topic>"` — math-explainer specialization; uses MathTex when LaTeX is available, else falls back to Text.

## Optional

- `--voice [gtts|openai|elevenlabs]` — narration via manim-voiceover (default: silent + narration script).
  - `gtts` is keyless. `openai` needs `OPENAI_API_KEY`. `elevenlabs` needs `ELEVENLABS_API_KEY`.
- `--quality low|medium|high|4k` — render quality; default `high` (1920x1080 @ 60fps).
- `--storyboard-only` — stop after producing storyboard.yaml; skip rendering.
- `--out <dir>` — override output directory; default `out/<run-id>/`.

## Activation

This command activates the **manim-video** skill, which orchestrates a 4-role pipeline (researcher + planner + implementer + main). See `skills/manim-video/SKILL.md` for the full flow.

## Examples

```
/manim-video --idea "Why is the sky blue?"
/manim-video --paper 1706.03762 --voice gtts
/manim-video --math "Pythagorean theorem" --quality high
/manim-video --paper ./research.pdf --storyboard-only
```
