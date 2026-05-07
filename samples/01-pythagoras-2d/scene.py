"""Sample 01 — Pythagoras 2D visual proof.

Render:
    python -m manim render -qm samples/01-pythagoras-2d/scene.py Pythagoras2DScene
"""
from manim import *  # noqa: F401, F403  — Manim scene files conventionally import *


class Pythagoras2DScene(Scene):
    """Three-act visual proof of a^2 + b^2 = c^2 using squares on sides."""

    def construct(self) -> None:
        # ---- scene_01: right triangle setup -----------------------------------
        v1, v2, v3 = ORIGIN, 3 * RIGHT, 4 * UP
        triangle = Polygon(v1, v2, v3, color="#4ADEDC", stroke_width=4)
        label_a = Text("a", font_size=36).next_to((v1 + v2) / 2, DOWN)
        label_b = Text("b", font_size=36).next_to((v1 + v3) / 2, LEFT)
        label_c = Text("c", font_size=36).next_to((v2 + v3) / 2, UP + RIGHT, buff=0.2)

        self.play(Create(triangle), run_time=2)
        self.play(Write(VGroup(label_a, label_b, label_c)), run_time=1.5)
        self.wait(0.5)

        # ---- scene_02: squares on each side -----------------------------------
        square_a = Square(side_length=3, color="#8B5CF6").next_to(triangle, DOWN, buff=0)
        square_b = Square(side_length=4, color="#F5E6C8").next_to(triangle, LEFT, buff=0)
        square_c = Square(side_length=5, color="#4ADEDC").rotate(PI / 4).next_to(
            triangle, UP + RIGHT, buff=0
        )

        self.play(
            LaggedStart(
                Create(square_a),
                Create(square_b),
                Create(square_c),
                lag_ratio=0.3,
            ),
            run_time=3,
        )
        self.wait(0.5)

        # ---- scene_03: equality -----------------------------------------------
        equation = Text("a^2 + b^2 = c^2", font_size=48).to_edge(DOWN)
        self.play(Write(equation), run_time=2)
        self.play(Indicate(equation), run_time=1.5)
        self.wait(0.5)
