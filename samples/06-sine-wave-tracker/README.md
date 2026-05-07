# 06 — Sine wave tracker

A `ValueTracker` sweeps from `-π` to `π` while a sine curve and a moving dot are recomputed every frame via `always_redraw`.

**Techniques:** `NumberPlane`, `ValueTracker`, `always_redraw`, `plot`, `Dot`, `c2p`. **No LaTeX required.**

**Render:**
```bash
python -m manim render -qm samples/06-sine-wave-tracker/scene.py SineWaveTrackerScene
```

**Files:** `storyboard.yaml` (2 scenes), `scene.py` (`SineWaveTrackerScene`), `out.mp4`, `thumb.png`.
