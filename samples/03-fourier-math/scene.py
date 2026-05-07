"""Sample 03 - Fourier series formula (schema 0.2.0 + chrome, LaTeX-free).

Render:
    python -m manim render -ql samples/03-fourier-math/scene.py Scene01
    python -m manim render -ql samples/03-fourier-math/scene.py Scene02
"""
from _shared import (
    PALETTE,
    add_header,
    add_title_card,
    play_with_captions,
)
from manim import *  # noqa: F401, F403

_TOTAL_SCENES = 2


class Scene01(Scene):
    """General Fourier series."""

    def construct(self) -> None:
        add_header(self, idx=1, total=_TOTAL_SCENES, title="General formula")
        add_title_card(self, "General formula", duration_s=1.5)

        general = Text(
            "f(x) = a0 + sum (an cos nx + bn sin nx)",
            font_size=36,
            color=PALETTE["primary"],
        ).shift(DOWN * 0.5)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Write(general), run_time=3)
            scene.play(Indicate(general), run_time=1.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "The general Fourier series writes any periodic function as a sum "
                "of cosines and sines with adjustable coefficients."
            ),
            total_s=4.5,
            voice_enabled=False,
        )
        self.wait(0.3)


class Scene02(Scene):
    """Expanded first three terms."""

    def construct(self) -> None:
        add_header(self, idx=2, total=_TOTAL_SCENES, title="Expanded first three terms")
        add_title_card(self, "Expanded first three terms", duration_s=1.5)

        expanded = Text(
            "f(x) = a0 + a1 cos x + b1 sin x + a2 cos 2x + b2 sin 2x + ...",
            font_size=28,
            color=PALETTE["primary"],
        ).shift(DOWN * 0.5)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Write(expanded), run_time=4)
            scene.play(Indicate(expanded), run_time=1.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "Expanded out, the first three terms read a zero plus a one cosine "
                "x plus b one sine x and so on."
            ),
            total_s=5.5,
            voice_enabled=False,
        )
        self.wait(0.3)
