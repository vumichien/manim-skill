"""Sample 05 - Text morph (schema 0.2.0 + chrome). Voice-free variant per plan.

Render:
    python -m manim render -ql samples/05-text-morph/scene.py Scene01
"""
from _shared import (
    PALETTE,
    add_header,
    play_with_captions,
)
from manim import *  # noqa: F401, F403

_TOTAL_SCENES = 1


class Scene01(Scene):
    """One word morphs into another via ReplacementTransform, then fades."""

    def construct(self) -> None:
        add_header(self, idx=1, total=_TOTAL_SCENES, title="Idea morphs into animation")

        word_idea = Text("idea", font_size=96, color=PALETTE["primary"])
        word_animation = Text("animation", font_size=96, color=PALETTE["accent"])

        def body(scene: Scene, _tracker) -> None:
            scene.play(Write(word_idea), run_time=1.5)
            scene.play(ReplacementTransform(word_idea, word_animation), run_time=2)
            scene.wait(0.3)
            scene.play(FadeOut(word_animation), run_time=1.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "An idea is just a starting point. Watch as the word morphs into "
                "animation, the medium that brings it to life."
            ),
            total_s=5.5,
            voice_enabled=False,
        )
        self.wait(0.3)
