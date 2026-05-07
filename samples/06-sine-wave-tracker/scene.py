"""Sample 06 — Sine wave traced by a ValueTracker-driven dot.

Render:
    python -m manim render -qm samples/06-sine-wave-tracker/scene.py SineWaveTrackerScene
"""
from manim import *  # noqa: F401, F403


class SineWaveTrackerScene(Scene):
    """A NumberPlane hosts y = sin(x); a dot rides the curve while the wave is drawn."""

    def construct(self) -> None:
        plane = NumberPlane(
            x_range=[-PI * 1.2, PI * 1.2, PI / 2],
            y_range=[-1.5, 1.5, 0.5],
            x_length=10,
            y_length=4,
            background_line_style={"stroke_opacity": 0.3},
        )
        label = Text("y = sin(x)", font_size=36, color="#F5E6C8").to_corner(UR)

        self.play(Create(plane), run_time=1.5)
        self.play(Write(label), run_time=1)

        # ValueTracker drives both the partial sine curve and the dot riding it.
        tracker = ValueTracker(-PI)

        curve = always_redraw(
            lambda: plane.plot(
                lambda x: np.sin(x),
                x_range=[-PI, tracker.get_value()],
                color="#4ADEDC",
                stroke_width=4,
            )
        )
        dot = always_redraw(
            lambda: Dot(
                point=plane.c2p(tracker.get_value(), np.sin(tracker.get_value())),
                color="#8B5CF6",
                radius=0.12,
            )
        )

        self.add(curve, dot)
        self.play(tracker.animate.set_value(PI), run_time=4, rate_func=linear)
        self.wait(0.8)
