"""Sample 05 — Text morph (idea -> animation).

Render:
    python -m manim render -qm samples/05-text-morph/scene.py TextMorphScene
"""
from manim import *  # noqa: F401, F403


class TextMorphScene(Scene):
    """One word morphs into another via ReplacementTransform, then fades."""

    def construct(self) -> None:
        word_idea = Text("idea", font_size=96, color="#4ADEDC")
        word_animation = Text("animation", font_size=96, color="#8B5CF6")

        self.play(Write(word_idea), run_time=1.5)
        self.play(ReplacementTransform(word_idea, word_animation), run_time=2)
        self.wait(0.5)
        self.play(FadeOut(word_animation), run_time=1.5)
