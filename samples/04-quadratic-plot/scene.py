"""Sample 04 — Plot y = x^2.

Render:
    python -m manim render -qm samples/04-quadratic-plot/scene.py QuadraticPlotScene
"""
from manim import *  # noqa: F401, F403


class QuadraticPlotScene(Scene):
    """Axes appear, then y = x^2 is drawn from left to right."""

    def construct(self) -> None:
        # Note: axes.add_coordinates() would render numeric tick labels via MathTex,
        # which requires LaTeX. We omit it so this sample is LaTeX-free.
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[0, 9, 1],
            x_length=6,
            y_length=4,
            tips=False,
        )
        parabola = axes.plot(lambda x: x ** 2, x_range=[-3, 3], color="#8B5CF6")
        label = Text("y = x^2", font_size=36).to_corner(UR)

        self.play(Create(axes), run_time=1.5)
        self.play(Create(parabola), run_time=4)
        self.play(Write(label), run_time=1.5)
        self.wait(0.5)
