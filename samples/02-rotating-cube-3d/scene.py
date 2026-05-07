"""Sample 02 - Rotating cube 3D (schema 0.2.0 + chrome).

Render:
    python -m manim render -ql samples/02-rotating-cube-3d/scene.py Scene01

ThreeDScene quirk: the chrome helpers' header is a 2D mobject. We re-add it as
``add_fixed_in_frame_mobjects`` so the 3D camera does not project it. Captions
also need fixed-in-frame, so ``play_with_captions`` is bypassed for this sample;
captions render via the SRT file generated post-render instead.
"""
from _shared import PALETTE, add_header
from manim import *  # noqa: F401, F403

_TOTAL_SCENES = 1


class Scene01(ThreeDScene):
    """Translucent cube spins around the Z axis with reference axes shown."""

    def construct(self) -> None:
        chrome = add_header(self, idx=1, total=_TOTAL_SCENES, title="Cube rotates around vertical axis")
        # 3D quirk: header must be fixed in frame so camera projection skips it.
        self.add_fixed_in_frame_mobjects(chrome)

        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)

        axes = ThreeDAxes(x_range=[-3, 3], y_range=[-3, 3], z_range=[-3, 3])
        cube = Cube(side_length=2, fill_opacity=0.6).set_color(PALETTE["primary"])

        self.play(Create(axes), run_time=1.5)
        self.play(FadeIn(cube), run_time=1)
        self.play(Rotate(cube, angle=TAU, axis=UP), run_time=5)
        self.wait(0.3)
