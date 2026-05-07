"""Trivial render fixture — used by test_render_runner.py to prove the pipeline works."""
from manim import *  # noqa: F401, F403


class HelloScene(Scene):
    def construct(self) -> None:
        self.play(Create(Circle()))
        self.wait(0.1)
