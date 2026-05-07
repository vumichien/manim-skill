# Storyboard Schema (v0.2.0)

The storyboard is the **only contract** between the planner and implementer agents. Schema drift breaks the pipeline.

JSON Schema source of truth: [`schemas/storyboard.schema.json`](../../../schemas/storyboard.schema.json) (Draft 2020-12).
Reference example: [`schemas/storyboard.example.yaml`](../../../schemas/storyboard.example.yaml).
Migration guide (0.1.x → 0.2.0): [`docs/storyboard-migration-0.2.0.md`](../../../docs/storyboard-migration-0.2.0.md).

## Top-level shape

```yaml
meta:    # required
  schema_version: "0.2.0"        # required since 0.2.0; literal string
  title: "<one-line title>"
  topic: "<short description>"
  source:
    kind: idea | math | paper
    ref: "<arxiv-id-or-url-or-null>"
  quality: low | medium | high | 4k
  voice: gtts | openai | elevenlabs | null   # default gtts (resolved by skill)
  total_duration_s: <number>     # 5..1800; sum of scenes ±1s
  transition_s: <number>         # 0.3..1.5; xfade duration; default 0.7
  palette:                       # optional; preset default applied if absent
    primary: "#4ADEDC"
    accent:  "#8B5CF6"
    warn:    "#F5E6C8"
    bg:      "#0F1B2D"
  show_progress: true            # default true; persistent header bar
  created_at: "<ISO-8601>"
  manim_version: "0.20.1"

scenes:  # required, 1..30
  - id: scene_01                 # ^scene_\d{2}$, contiguous from 01
    title: "<one-line>"
    beat: "<what happens, prose>"
    duration_s: <number>         # 1..90
    scene_class: Scene | MovingCameraScene | ThreeDScene | ZoomedScene | VoiceoverScene
    show_title_card: true        # default true; opening title card
    mobjects: [...]
    animations: [...]            # ≥1
    voiceover_text: "<5+ words>" # REQUIRED since 0.2.0
    captions: [...]              # optional; default auto-chunk from voiceover_text
    notes: "<implementer hints, free text>" # optional
```

## New fields in 0.2.0

| Field | Required | Range/Default | Purpose |
|---|---|---|---|
| `meta.schema_version` | yes | literal `"0.2.0"` | Version gate. Validator rejects older. |
| `meta.transition_s` | no | 0.3–1.5, default 0.7 | xfade duration between scenes. |
| `meta.palette` | no | 4 hex codes | Brand palette overriding chrome defaults. |
| `meta.show_progress` | no | bool, default true | Persistent header bar. |
| `scene.show_title_card` | no | bool, default true | Animated title card on this scene. |
| `scene.captions[]` | no | array | Explicit caption schedule; empty = auto-chunk. |
| `scene.voiceover_text` | **yes** | 5+ words, ≤2000 chars | Drives TTS + captions. Validator enforces. |

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

## `captions[]` (optional, 0.2.0)

```yaml
captions:
  - { text: "A right triangle appears", start_s: 0.0, duration_s: 2.0 }
  - { text: "Legs labeled a and b",     start_s: 2.0, duration_s: 2.0 }
```

When empty, implementer auto-chunks `voiceover_text` (~10 words per chunk, distributed across `scene.duration_s`). Populate only when a specific word must coincide with a specific animation.

## Validation gate

After the planner emits `storyboard.yaml`, the skill runs:

```
python scripts/validate-storyboard.py <out>/storyboard.yaml
```

Schema errors fail with a JSON-Pointer-style path. Cross-check errors include:
- `schema_version` missing or below 0.2.0 (with link to migration doc).
- `voiceover_text` empty/whitespace-only or under 5 words.
- Animation `target` does not match any `mobjects[].name` in the scene.
- Sum of `scenes[].duration_s` ≠ `meta.total_duration_s` (±1s tolerance).
- Scene IDs not contiguous (`scene_01, scene_02, …`).

Caption-overflow is a **warning** (printed to stderr) not a failure.

Validator exits 0 on success. If non-zero, the skill re-spawns the planner ONCE with the validator's stderr. Two failures escalate to the user.

## Author guidelines (for the planner)

1. **One concept per scene.** If a scene needs more than ~6 mobjects to set up, split it.
2. **Durations:** 6–15s for a typical "introduce + animate + hold" scene; 30s upper for complex transformations. Long scenes blow the render budget.
3. **Always name shared mobjects.** Anonymous (`name`-less) entries can be referenced only by index, which is brittle when scenes grow.
4. **Prefer `Text` over `MathTex`** unless the topic requires math typesetting. `Text` works without LaTeX and renders 10× faster.
5. **`voiceover_text` is required and drives captions.** See `voiceover-text-style.md` — present-tense, 5–25 words per 10s, three-beat structure.
6. **Body mobjects in y in [-3.0, 3.0].** Chrome occupies the top and bottom 0.5 units of the frame. Use `notes` to flag tight scenes.
7. **End-of-scene wait is fixed at 0.3s.** Compose `duration_s = title_card_s + body_anim_sum + 0.3`.
8. **`notes`** is the place to leave implementer hints that don't fit the structured fields (e.g. "use `MovingCameraScene` for the zoom on the inner square").

## Example (Pythagoras, 3 scenes)

See [`schemas/storyboard.example.yaml`](../../../schemas/storyboard.example.yaml) and the gold-reference at [`samples/01-pythagoras-2d/storyboard.yaml`](../../../samples/01-pythagoras-2d/storyboard.yaml).
