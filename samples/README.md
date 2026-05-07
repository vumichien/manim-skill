# Samples

Six reference animations covering the core Manim surface area: 2D geometry, 3D, math typesetting, plotting, text transforms, and updater-driven animation.

Each sample is **hand-coded** as a reference — pair it with its `storyboard.yaml` to see the planner→implementer translation at work.

## Index

| # | Slug | Demonstrates | LaTeX? | Duration |
|---|---|---|---|---|
| 01 | [pythagoras-2d](01-pythagoras-2d/) | Polygon, Square, LaggedStart, Indicate | no | 16s |
| 02 | [rotating-cube-3d](02-rotating-cube-3d/) | ThreeDScene, ThreeDAxes, Cube, Rotate | no | 8s |
| 03 | [fourier-math](03-fourier-math/) | MathTex, ReplacementTransform | **yes** | 12s |
| 04 | [quadratic-plot](04-quadratic-plot/) | Axes, plot lambda, add_coordinates | no | 8s |
| 05 | [text-morph](05-text-morph/) | Text, ReplacementTransform, FadeOut | no | 6s |
| 06 | [sine-wave-tracker](06-sine-wave-tracker/) | NumberPlane, ValueTracker, always_redraw | no | 7s |

## Build all samples

After `pwsh scripts/install.ps1` (or `bash scripts/install.sh`) succeeds, populate the `out.mp4` + `thumb.png` for every sample with:

```powershell
pwsh samples/build-samples.ps1
```

```bash
bash samples/build-samples.sh
```

The script renders each `scene.py` at `-qm` (1280×720, 30fps) into `<sample-dir>/out.mp4` and grabs a frame near the end of the clip (≈80 % of duration, via `ffmpeg -ss`) as `<sample-dir>/thumb.png` — sampling from the mp4 instead of `--save_last_frame` so fade-out scenes still produce a visible thumb. Sample 03 is skipped automatically if `xelatex` is not on PATH; a pre-rendered placeholder thumb ships with the repo so the README grid stays complete.

## What each sample is for

- **Reference for the implementer agent.** When the agent needs to know "how do I render a 3D cube" it can grep `samples/02-*/scene.py`.
- **Test fixtures.** Storyboards are validated in CI (Phase 10) so schema drift breaks the build.
- **README hero grid.** Thumbnails are reused in the top-level `README.md` showcase.
- **First-time-user demo.** New users render these to verify their install works end-to-end.
