"""Sample 01 - Pythagoras 2D visual proof (schema 0.2.0 + chrome).

Render each scene individually:
    python -m manim render -ql samples/01-pythagoras-2d/scene.py Scene01
    python -m manim render -ql samples/01-pythagoras-2d/scene.py Scene02
    python -m manim render -ql samples/01-pythagoras-2d/scene.py Scene03

This sample uses the voice-free path (Scene base + caption-only) so it renders
offline. To exercise voice path, swap base class to ``VoiceoverScene`` and
``set_speech_service(GTTSService(lang="en"))`` as documented in voiceover-setup.md.
"""
from _shared import (
    PALETTE,
    add_header,
    add_title_card,
    play_with_captions,
)
from manim import *  # noqa: F401, F403  # Manim scene files conventionally import *

_TOTAL_SCENES = 3


class Scene01(Scene):
    """Right triangle setup."""

    def construct(self) -> None:
        add_header(self, idx=1, total=_TOTAL_SCENES, title="Right triangle setup")
        add_title_card(self, "Right triangle setup", duration_s=1.5)

        v1, v2, v3 = ORIGIN, 3 * RIGHT, 4 * UP
        triangle = Polygon(v1, v2, v3, color=PALETTE["primary"], stroke_width=4)
        label_a = Text("a", font_size=36).next_to((v1 + v2) / 2, DOWN)
        label_b = Text("b", font_size=36).next_to((v1 + v3) / 2, LEFT)
        label_c = Text("c", font_size=36).next_to((v2 + v3) / 2, UP + RIGHT, buff=0.2)
        # Keep body within y in [-3.0, 3.0] so chrome does not collide.
        body_group = VGroup(triangle, label_a, label_b, label_c).shift(DOWN * 0.5)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Create(triangle), run_time=2)
            scene.play(Write(VGroup(label_a, label_b, label_c)), run_time=1.5)
            scene.wait(0.7)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "Start with a right triangle. The two legs are labeled a and b, "
                "and the hypotenuse is c."
            ),
            total_s=4.2,
            voice_enabled=False,
        )
        self.wait(0.3)
        # Reference body_group to silence linter; it's the layout anchor.
        _ = body_group


class Scene02(Scene):
    """Squares on each side."""

    def construct(self) -> None:
        add_header(self, idx=2, total=_TOTAL_SCENES, title="Squares on each side")
        add_title_card(self, "Squares on each side", duration_s=1.5)

        v1, v2, v3 = ORIGIN, 3 * RIGHT, 4 * UP
        triangle = Polygon(v1, v2, v3, color=PALETTE["primary"], stroke_width=4)
        # Squares anchored against each leg / hypotenuse.
        square_a = Square(side_length=3, color=PALETTE["accent"]).next_to(
            triangle, DOWN, buff=0
        )
        square_b = Square(side_length=4, color=PALETTE["warn"]).next_to(
            triangle, LEFT, buff=0
        )
        square_c = (
            Square(side_length=5, color=PALETTE["primary"])
            .rotate(PI / 4)
            .next_to(triangle, UP + RIGHT, buff=0)
        )
        body_group = VGroup(triangle, square_a, square_b, square_c).scale(0.55).shift(
            DOWN * 0.3
        )

        def body(scene: Scene, _tracker) -> None:
            scene.play(Create(triangle), run_time=1)
            scene.play(
                LaggedStart(
                    Create(square_a),
                    Create(square_b),
                    Create(square_c),
                    lag_ratio=0.3,
                ),
                run_time=3,
            )
            scene.wait(0.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "Build three squares, one on each side. Their sizes are a "
                "squared, b squared, and c squared."
            ),
            total_s=4.5,
            voice_enabled=False,
        )
        self.wait(0.3)
        _ = body_group


class Scene03(Scene):
    """Final equality."""

    def construct(self) -> None:
        add_header(self, idx=3, total=_TOTAL_SCENES, title="Equality")

        equation = Text(
            "a^2 + b^2 = c^2",
            font_size=48,
            color=PALETTE["primary"],
        ).move_to(ORIGIN)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Write(equation), run_time=2)
            scene.play(Indicate(equation), run_time=1.5)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "The two smaller square areas sum exactly to the area of the "
                "square on the hypotenuse."
            ),
            total_s=3.5,
            voice_enabled=False,
        )
        self.wait(0.3)
