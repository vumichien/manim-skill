"""NameError fixture — `Cricle` is a typo. Used to verify render-runner classifier."""
from manim import *  # noqa: F401, F403


class NameErrorScene(Scene):
    def construct(self) -> None:
        self.play(Create(Cricle()))  # noqa: F821 — intentional typo for negative test
        self.wait(0.1)
