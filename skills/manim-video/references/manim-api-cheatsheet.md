# Manim API Cheatsheet

Distilled from Manim Community 0.20.x for headless authoring. Read only the section you need.

## Scene classes

| Class | Use when |
|---|---|
| `Scene` | Default — 2D animations, no camera moves |
| `MovingCameraScene` | You need to pan/zoom: `self.camera.frame.animate.move_to(...)` |
| `ThreeDScene` | 3D objects: `self.set_camera_orientation(phi=..., theta=...)` |
| `ZoomedScene` | Inset zoom (rare) |
| `VoiceoverScene` | Narration sync via manim-voiceover |

## Mobjects (whitelist matches `schemas/storyboard.schema.json`)

**Text/math**
- `Text("hello", font_size=36)` — fast, no LaTeX
- `MathTex(r"\frac{x}{2}")` — formula; **requires LaTeX**
- `Tex(r"$x = 2$")` — full LaTeX doc; rare
- `MarkupText("<b>bold</b>")` — Pango markup

**2D shapes**
- `Square(side_length=2)`, `Circle(radius=1)`, `Rectangle(width=4, height=2)`
- `Triangle()`, `Polygon(*points)`, `RegularPolygon(n=6)`
- `Line(start, end)`, `Arrow(start, end, buff=0)`, `Vector([x, y])`
- `Arc(radius=1, angle=PI)`, `Ellipse()`, `Dot(point, radius=0.05)`

**Plots**
- `Axes(x_range=[-3, 3], y_range=[-2, 2], axis_config={"color": BLUE})`
- `NumberPlane()`, `PolarPlane()`
- `axes.plot(lambda x: x**2)` — function graph on axes
- `ParametricFunction(lambda t: (cos(t), sin(t), 0), t_range=[0, TAU])`

**3D**
- `ThreeDAxes()`, `Sphere()`, `Cube()`, `Cone()`, `Cylinder()`, `Torus()`
- `Surface(lambda u, v: (u, v, u*v), u_range=[-2,2], v_range=[-2,2])`

**Groups**
- `VGroup(a, b, c)` — vector group, common
- `Group(a, b, c)` — generic group (used for non-vector mobjects)

## Animations

**Entry**
- `Create(obj)` — draw paths
- `Write(text)` — stroke-by-stroke for Text/MathTex
- `DrawBorderThenFill(shape)` — outline then fill
- `FadeIn(obj, shift=UP)`, `GrowFromCenter(obj)`, `GrowFromEdge(obj, edge=LEFT)`

**Exit**
- `FadeOut(obj)`, `Uncreate(obj)`

**Morph**
- `Transform(old, new)` — old replaced by new
- `ReplacementTransform(old, new)` — same, semantically clearer
- `TransformMatchingTex(eq1, eq2)` — preserves matching MathTex parts

**Motion**
- `MoveAlongPath(obj, path)`, `Rotate(obj, angle=PI)`
- `obj.animate.shift(RIGHT)`, `obj.animate.scale(2)` — anim by method chaining

**Emphasis**
- `Indicate(obj)` — flash highlight
- `Wiggle(obj)`, `Flash(point)`, `Circumscribe(obj)`

**Composition**
- `LaggedStart(a, b, c, lag_ratio=0.5)` — staggered
- `Succession(a, b, c)` — sequential
- `AnimationGroup(a, b, c)` — parallel (same as passing multiple to `self.play`)

## Boilerplate

```python
from manim import *

class MyScene(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        label = Text("hello").next_to(circle, DOWN)

        self.play(Create(circle), Write(label), run_time=2)
        self.play(circle.animate.shift(RIGHT * 2), run_time=1)
        self.wait(1)
```

## Voiceover (when --voice flag is set)

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class MyVoiced(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))
        with self.voiceover(text="A circle appears.") as t:
            self.play(Create(Circle()), run_time=t.duration)
```

Provider swap: `GTTSService` → `OpenAIService(voice="fable")` or `ElevenLabsService(voice_name="Adam")`. Env vars in `voiceover-setup.md`.

## Chrome helpers (schema 0.2.0)

The implementer emits `out/<run-id>/scenes/_shared.py` from the template at
`skills/manim-video/references/shared-chrome-template.py`, then each per-scene file
imports four helpers:

```python
from _shared import PALETTE, add_header, add_title_card, chunk_captions, play_with_captions
```

| Helper | Purpose |
|---|---|
| `PALETTE` | dict of hex codes — `primary`, `accent`, `warn`, `bg` |
| `add_header(scene, idx, total, title)` | top progress bar + title + counter; instant `add` |
| `add_title_card(scene, title, duration_s=1.5)` | full-frame opener; FadeIn → hold → FadeOut |
| `chunk_captions(text, total_s, words_per_chunk=10)` | split narration into time-sliced caption tuples |
| `play_with_captions(scene, body, voiceover_text, total_s, voice_enabled)` | wrap body anims with caption track + optional voice |

Layout invariants the planner enforces so chrome does not collide with body mobjects:
- Header occupies y in `[3.1, 3.5]`. Body mobjects: `y ≤ 3.0`.
- Captions anchor to bottom edge (`buff=0.5`). Body mobjects: `y ≥ -3.0`.

Per-scene file pattern (voice path):

```python
"""Scene 01: Set up the right triangle"""
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
from _shared import PALETTE, add_header, add_title_card, play_with_captions

class Scene01(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))
        add_header(self, idx=1, total=3, title="Set up the right triangle")
        add_title_card(self, "Set up the right triangle", duration_s=1.5)

        def body(scene, tracker):
            tri = Polygon([0,0,0],[3,0,0],[0,4,0], color=PALETTE["primary"])
            scene.play(Create(tri), run_time=2)
            # ... rest of scene body

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text="Start with a right triangle...",
            total_s=8.0,
            voice_enabled=True,
        )
        self.wait(0.3)
```

Voice-free variant: change base class to `Scene`, drop `set_speech_service`, pass
`voice_enabled=False`. Captions still render via the updater track.

## Critical pitfalls

1. **`self.add(circle)` vs `self.play(Create(circle))`** — `add` puts the object on screen instantly; `play(Create(...))` animates the appearance. Mixing them on the same object hides the animation.

2. **MathTex without LaTeX → empty render.** No traceback. Pre-check `xelatex --version`. If absent, fall back to `Text(r"a^2 + b^2 = c^2")` (no rendering of LaTeX, but visible).

3. **`run_time` on grouped animations** — `self.play(LaggedStart(a, b, c), run_time=3)` controls the *whole group*, not each member.

4. **Camera moves require `MovingCameraScene` or `ThreeDScene`** — calling `self.camera.frame.animate...` on a base `Scene` errors at runtime.

5. **Coordinates** — Manim uses a custom unit system; the screen frame is roughly 14×8 wide × tall in Manim units. `ORIGIN` is screen center. `UP`, `DOWN`, `LEFT`, `RIGHT` are unit vectors of length 1.

## Headless render

```bash
python -m manim render -qh --media_dir <out>/manim_media <scene_file> <ClassName>
```

Quality flags: `-ql` (480p15), `-qm` (720p30), `-qh` (1080p60, default), `-qk` (4K60). Add `--dry_run` to validate without rendering, `--format gif` for GIF.

Output lands at `<media_dir>/videos/<scene_stem>/<quality_dir>/<ClassName>.mp4`. Use `scripts/render.py` for a structured-JSON wrapper.

## Authoritative sources

- https://docs.manim.community/en/stable/
- https://docs.manim.community/en/stable/examples.html
- https://voiceover.manim.community/en/stable/
