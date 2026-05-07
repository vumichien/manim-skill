"""Sample 04 - Quadratic plot (schema 0.2.0 + chrome).

Render:
    python -m manim render -ql samples/04-quadratic-plot/scene.py Scene01
"""
from _shared import (
    PALETTE,
    add_header,
    add_title_card,
    play_with_captions,
)
from manim import *  # noqa: F401, F403

_TOTAL_SCENES = 1


class Scene01(Scene):
    """Axes appear, then y = x^2 is drawn from left to right."""

    def construct(self) -> None:
        add_header(self, idx=1, total=_TOTAL_SCENES, title="Axes and parabola")
        add_title_card(self, "Axes and parabola", duration_s=1.5)

        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[0, 9, 1],
            x_length=6,
            y_length=4,
            tips=False,
        )
        parabola = axes.plot(
            lambda x: x ** 2, x_range=[-3, 3], color=PALETTE["accent"]
        )
        # Body shifted DOWN 0.5 so axes top stays under header (y < 3.0).
        body_group = VGroup(axes, parabola).shift(DOWN * 0.4)
        label = Text("y = x^2", font_size=36, color=PALETTE["primary"]).to_corner(UR).shift(DOWN * 0.7)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Create(axes), run_time=1.5)
            scene.play(Create(parabola), run_time=4)
            scene.play(Write(label), run_time=1.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "Plot the parabola y equals x squared. Axes appear first, then the "
                "curve sweeps from left to right."
            ),
            total_s=7.0,
            voice_enabled=False,
        )
        self.wait(0.3)
        _ = body_group
