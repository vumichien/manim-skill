"""Sample 06 - Sine wave tracker (schema 0.2.0 + chrome).

Render:
    python -m manim render -ql samples/06-sine-wave-tracker/scene.py Scene01
    python -m manim render -ql samples/06-sine-wave-tracker/scene.py Scene02
"""
from _shared import (
    PALETTE,
    add_header,
    play_with_captions,
)
from manim import *  # noqa: F401, F403

_TOTAL_SCENES = 2


def _make_plane() -> NumberPlane:
    return NumberPlane(
        x_range=[-PI * 1.2, PI * 1.2, PI / 2],
        y_range=[-1.5, 1.5, 0.5],
        x_length=10,
        y_length=4,
        background_line_style={"stroke_opacity": 0.3},
    ).shift(DOWN * 0.4)


class Scene01(Scene):
    """A NumberPlane appears with a y = sin(x) label."""

    def construct(self) -> None:
        add_header(self, idx=1, total=_TOTAL_SCENES, title="Plane and label")

        plane = _make_plane()
        label = Text("y = sin(x)", font_size=36, color=PALETTE["warn"]).to_corner(UR).shift(DOWN * 0.7)

        def body(scene: Scene, _tracker) -> None:
            scene.play(Create(plane), run_time=1.5)
            scene.play(Write(label), run_time=1)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "A coordinate plane appears with the label y equals sine of x. "
                "We will trace the curve next."
            ),
            total_s=2.5,
            voice_enabled=False,
        )
        self.wait(0.3)


class Scene02(Scene):
    """A ValueTracker drives a dot riding y = sin(x) while the curve is drawn."""

    def construct(self) -> None:
        add_header(self, idx=2, total=_TOTAL_SCENES, title="Dot rides the sine curve")

        plane = _make_plane()
        label = Text("y = sin(x)", font_size=36, color=PALETTE["warn"]).to_corner(UR).shift(DOWN * 0.7)
        # Plane re-emitted instantly (no animation) so scene is self-contained.
        self.add(plane, label)

        tracker = ValueTracker(-PI)

        curve = always_redraw(
            lambda: plane.plot(
                lambda x: np.sin(x),
                x_range=[-PI, tracker.get_value()],
                color=PALETTE["primary"],
                stroke_width=4,
            )
        )
        dot = always_redraw(
            lambda: Dot(
                point=plane.c2p(tracker.get_value(), np.sin(tracker.get_value())),
                color=PALETTE["accent"],
                radius=0.12,
            )
        )

        def body(scene: Scene, _tracker) -> None:
            scene.add(curve, dot)
            scene.play(tracker.animate.set_value(PI), run_time=4, rate_func=linear)

        play_with_captions(
            self,
            body_callable=body,
            voiceover_text=(
                "A value tracker sweeps from minus pi to pi. The curve and dot "
                "redraw each frame, tracing the sine wave."
            ),
            total_s=4.5,
            voice_enabled=False,
        )
        self.wait(0.3)
