# Samples

Six reference animations covering the core Manim surface area: 2D geometry, 3D, math typesetting, plotting, text transforms, and updater-driven animation.

Each sample is **hand-coded** as a reference — pair it with its `storyboard.yaml` to see the planner→implementer translation at work. All samples target schema 0.2.0 (chrome header + captions + cross-fade transitions). Each sample directory ships a local `_shared.py` (copy of `skills/manim-video/references/shared-chrome-template.py`) so `scene.py` can `from _shared import ...` without altering Python path.

## Index

| # | Slug | Demonstrates | LaTeX? | Scenes | Duration |
|---|---|---|---|---|---|
| 01 | [pythagoras-2d](01-pythagoras-2d/) | Polygon, Square, LaggedStart, Indicate, chrome | no | 3 | 18s |
| 02 | [rotating-cube-3d](02-rotating-cube-3d/) | ThreeDScene, ThreeDAxes, Cube, Rotate, fixed-in-frame chrome | no | 1 | 9s |
| 03 | [fourier-math](03-fourier-math/) | Text (LaTeX-free since 0.2.0), Indicate | no | 2 | 12s |
| 04 | [quadratic-plot](04-quadratic-plot/) | Axes, plot lambda, label | no | 1 | 9s |
| 05 | [text-morph](05-text-morph/) | Text, ReplacementTransform, FadeOut, voice-free variant | no | 1 | 6s |
| 06 | [sine-wave-tracker](06-sine-wave-tracker/) | NumberPlane, ValueTracker, always_redraw | no | 2 | 8s |

## Build all samples

After `pwsh scripts/install.ps1` (or `bash scripts/install.sh`) succeeds, populate `out.mp4` + `thumb.png` for every sample with:

```powershell
pwsh samples/build-samples.ps1
```

```bash
bash samples/build-samples.sh
```

The script renders each Scene class at `-qm` (1280×720, 30fps), then concatenates per-scene mp4s into `<sample-dir>/out.mp4` via `scripts/concat-xfade.py` with cross-fade transitions. Single-scene samples copy the mp4 directly. Thumbnails are sampled at ~80% of the final video duration via `ffmpeg -ss`.

## Render a single scene

Each sample uses the multi-class pattern (`Scene01`, `Scene02`, ...). To render one scene:

```bash
python -m manim render -ql samples/01-pythagoras-2d/scene.py Scene01
```

## What each sample is for

- **Reference for the implementer agent.** When the agent needs to know "how do I render a 3D cube" it can grep `samples/02-*/scene.py`.
- **Test fixtures.** Storyboards are validated in CI (Phase 10) so schema drift breaks the build.
- **README hero grid.** Thumbnails are reused in the top-level `README.md` showcase.
- **First-time-user demo.** New users render these to verify their install works end-to-end.
