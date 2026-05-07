# Render Runner Contract

`scripts/render.py` is a single-shot subprocess wrapper around `python -m manim render`. Implementer agents call it per scene and read the JSON return value to decide whether to retry, patch the scene, or move on.

## Invocation

```bash
python scripts/render.py \
  --scene-file out/<run>/scenes/scene_01.py \
  --class-name Scene01 \
  --quality high \
  --out-dir out/<run> \
  [--dry-run] [--gif] [--timeout 600]
```

Args:
- `--scene-file PATH` (required) — Python file containing the Manim Scene subclass.
- `--class-name CLS` (required) — Scene subclass name to render.
- `--quality {low,medium,high,4k}` — default `high`.
- `--out-dir DIR` (required) — `manim_media/` is created underneath this dir.
- `--dry-run` — validates syntax, skips rendering. Use this as the first attempt to fail fast.
- `--gif` — render as `.gif` instead of `.mp4` (uses `--format gif`).
- `--timeout N` — seconds; default 600.

## Return JSON (on stdout)

Exactly one JSON object printed to stdout (pretty-printed but newline-terminated). Parse it; do not parse stderr.

```json
{
  "ok": true,
  "exit_code": 0,
  "render_time_s": 87.3,
  "output_path": "out/260507-1530-pythag/manim_media/videos/scene_01/1080p60/Scene01.mp4",
  "error_class": null,
  "stderr_tail": "",
  "command": ["python", "-m", "manim", "render", "-qh", "..."]
}
```

On failure:

```json
{
  "ok": false,
  "exit_code": 1,
  "render_time_s": 12.0,
  "output_path": null,
  "error_class": "name",
  "stderr_tail": "...\nNameError: name 'CircleX' is not defined\n",
  "command": ["python", "-m", "manim", "render", "-ql", "..."]
}
```

## `error_class` semantics

| Class | Trigger pattern (regex against stderr) | Implementer action |
|---|---|---|
| `latex` | `latex.*(returned non-zero|failed|error)` or `xelatex|miktex` | Replace `MathTex(...)` calls with `Text(...)` and retry. Surface to summary if user passed `--math`. |
| `import` | `ModuleNotFoundError|ImportError` | Likely missing dep; instruct user to re-run install script. |
| `name` | `NameError: name '\w+' is not defined` | Patch the scene file (typo, missing import, wrong mobject ctor). |
| `type` | `TypeError` | Bad kwargs; look up the Mobject's signature and adjust. |
| `timeout` | (subprocess.TimeoutExpired) | Reduce scene complexity, drop quality to `medium`, or split into sub-scenes. |
| `other` | default | Read `stderr_tail` and apply best-judgment patch. |

## Retry pattern (implementer agent)

```
budget = 5
for attempt in 1..budget:
    # Step A: dry-run for fast feedback
    res = render(scene, dry_run=True)
    if not res.ok:
        patch(scene, res)
        continue

    # Step B: real render
    res = render(scene, dry_run=False)
    if res.ok:
        log(success); break
    patch(scene, res)

if attempt > budget:
    log(failure with last stderr_tail)
    move on to next scene
```

## Output paths

Manim writes to `<media_dir>/videos/<scene_stem>/<quality_dir>/<ClassName>.<ext>`, where:
- `<scene_stem>` is the scene file's basename without extension (e.g. `scene_01`)
- `<quality_dir>` follows Manim's convention: `480p15`, `720p30`, `1080p60`, `2160p60`
- `<ext>` is `mp4` (default) or `gif` (with `--gif`)

`render.py` populates `output_path` by checking the canonical location first, then falling back to a recursive glob for the class name. The path is returned as POSIX (forward slashes) for cross-platform safety.

## What this script intentionally does **not** do

- It does not implement the retry loop (that is the implementer agent's job).
- It does not concatenate scenes into a final video — use `scripts/concat-xfade.py` (schema 0.2.0+).
- It does not modify scene files; it is read-only on inputs.
- It does not stream stdout to the caller; it captures everything and emits one JSON object at the end.

## Implementer-side log fields (schema 0.2.0)

When the implementer appends the render JSON to `<out_dir>/render.log`, it should also include:

- `chrome_emitted`: bool — true if the scene file called `add_header` / `add_title_card`.
- `voice_path`: `"gtts" | "openai" | "elevenlabs" | "fallback_caption_only" | "none"`.
- `scene_duration_s`: float — the storyboard scene duration (used by `emit-captions-srt.py`).

These fields are added to each render attempt's JSON line so downstream tooling
(captions emission, summary report) can reason about chrome and voice without
re-reading the storyboard.
