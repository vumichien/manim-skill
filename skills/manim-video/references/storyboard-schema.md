# Storyboard Schema

The storyboard is the **only contract** between the planner and implementer agents. Schema drift breaks the pipeline.

JSON Schema source of truth: [`schemas/storyboard.schema.json`](../../../schemas/storyboard.schema.json) (Draft 2020-12).
Reference example: [`schemas/storyboard.example.yaml`](../../../schemas/storyboard.example.yaml).

## Top-level shape

```yaml
meta:    # required
  title: "<one-line title>"
  topic: "<short description>"
  source:
    kind: idea | math | paper
    ref: "<arxiv-id-or-url-or-null>"
  quality: low | medium | high | 4k
  voice: gtts | openai | elevenlabs | null
  total_duration_s: <number>     # 5..1800; sum of scenes ±1s
  created_at: "<ISO-8601>"
  manim_version: "0.20.1"

scenes:  # required, 1..30
  - id: scene_01                 # ^scene_\d{2}$, contiguous from 01
    title: "<one-line>"
    beat: "<what happens, prose>"
    duration_s: <number>         # 1..90
    scene_class: Scene | MovingCameraScene | ThreeDScene | ZoomedScene | VoiceoverScene
    mobjects: [...]
    animations: [...]            # ≥1
    voiceover_text: "<text>" | null
    notes: "<implementer hints, free text>" # optional
```

## `mobjects[]`

```yaml
- type: Square                   # whitelisted PascalCase Manim class
  name: red_box                  # optional, lowercase id used by animations
  content: "label text"          # only for Text/MathTex/Tex/MarkupText
  position: UP | [x, y] | [x, y, z]   # optional anchor
  kwargs:                        # optional ctor kwargs forwarded verbatim
    color: "#FF6B6B"
    side_length: 2
```

The `type` field accepts any class in the whitelist (Text, MathTex, Square, Circle, Polygon, Axes, NumberPlane, ParametricFunction, Surface, ThreeDAxes, Sphere, Cube, VGroup, …). Less common classes can use any PascalCase name; the implementer maps them to the actual Manim API at scene-emit time.

## `animations[]`

```yaml
- target: red_box                              # mobject name
  anim: Create                                 # whitelisted enum
  duration: 2.0                                # 0.1..30 seconds
  kwargs: { run_time: 2.0, lag_ratio: 0.5 }    # forwarded to the Animation ctor
```

Target reference forms:
- **By name:** `red_box` — must match a `mobjects[].name` in the same scene.
- **By index:** `mobjects[0]` — fallback when the planner skipped naming.
- **Group:** `VGroup(red_box, label_a)` — composes a transient group for the animation.

Animation enum (subset): `Create, Write, DrawBorderThenFill, FadeIn, FadeOut, Transform, ReplacementTransform, MoveAlongPath, Rotate, Indicate, LaggedStart, Succession, AnimationGroup`. See `manim-api-cheatsheet.md` for full list.

## Validation gate

After the planner emits `storyboard.yaml`, the skill runs:

```
python scripts/validate-storyboard.py <out>/storyboard.yaml
```

Schema errors fail with a JSON-Pointer-style path. Cross-check errors include:
- Animation `target` does not match any `mobjects[].name` in the scene.
- Sum of `scenes[].duration_s` ≠ `meta.total_duration_s` (±1s tolerance).
- Scene IDs not contiguous (`scene_01, scene_02, …`).

Validator exits 0 on success. If non-zero, the skill re-spawns the planner ONCE with the validator's stderr. Two failures escalate to the user.

## Author guidelines (for the planner)

1. **One concept per scene.** If a scene needs more than ~6 mobjects to set up, split it.
2. **Durations:** 6–15s for a typical "introduce + animate + hold" scene; 30s upper for complex transformations. Long scenes blow the render budget.
3. **Always name shared mobjects.** Anonymous (`name`-less) entries can be referenced only by index, which is brittle when scenes grow.
4. **Prefer `Text` over `MathTex`** unless the topic requires math typesetting. `Text` works without LaTeX and renders 10× faster.
5. **Voiceover beats.** When `meta.voice` is set, populate `voiceover_text` for every scene. Sentences map 1:1 to scene duration via `tracker.duration`.
6. **`notes`** is the place to leave implementer hints that don't fit the structured fields (e.g. "use `MovingCameraScene` for the zoom on the inner square").

## Example (Pythagoras, 3 scenes)

See [`schemas/storyboard.example.yaml`](../../../schemas/storyboard.example.yaml) for the canonical reference.
