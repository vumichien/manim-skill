"""Sample 02 — Rotating cube in 3D.

Render:
    python -m manim render -qm samples/02-rotating-cube-3d/scene.py RotatingCube3DScene
"""
from manim import *  # noqa: F401, F403


class RotatingCube3DScene(ThreeDScene):
    """Translucent cube spins around the Z axis with reference axes shown."""

    def construct(self) -> None:
        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)

        axes = ThreeDAxes(x_range=[-3, 3], y_range=[-3, 3], z_range=[-3, 3])
        cube = Cube(side_length=2, fill_opacity=0.6).set_color("#4ADEDC")

        self.play(Create(axes), run_time=1.5)
        self.play(FadeIn(cube), run_time=1)
        self.play(Rotate(cube, angle=TAU, axis=UP), run_time=5)
        self.wait(0.5)
