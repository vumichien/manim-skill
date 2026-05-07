"""Sample 03 — Fourier series formula. **Requires LaTeX (xelatex on PATH).**

Render:
    python -m manim render -qm samples/03-fourier-math/scene.py FourierMathScene
"""
from manim import *  # noqa: F401, F403


class FourierMathScene(Scene):
    """General Fourier series, then expanded to the first explicit terms."""

    def construct(self) -> None:
        general = MathTex(
            r"f(x) = a_0 + \sum_{n=1}^{\infty} \left( a_n \cos(nx) + b_n \sin(nx) \right)",
            font_size=56,
        )
        self.play(Write(general), run_time=3)
        self.play(Indicate(general), run_time=1.5)
        self.wait(0.5)

        expanded = MathTex(
            r"f(x) = a_0 + a_1 \cos(x) + b_1 \sin(x) + a_2 \cos(2x) + b_2 \sin(2x) + \cdots",
            font_size=40,
        )
        self.play(ReplacementTransform(general, expanded), run_time=2)
        self.play(Indicate(expanded), run_time=1.5)
        self.wait(0.5)
