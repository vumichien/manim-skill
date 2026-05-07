"""Shared chrome helpers for storyboard-driven Manim scenes (schema 0.2.0).

Implementer copies this file verbatim into ``out/<run-id>/scenes/_shared.py`` and
substitutes ``PALETTE`` from ``storyboard.meta.palette``. Per-scene imports::

    from _shared import PALETTE, add_header, add_title_card, chunk_captions, play_with_captions

LaTeX-free. Layout: header y in [3.1, 3.5], captions bottom-edge; planner keeps body
mobjects in y in [-3.0, 3.0].
"""
from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    FadeIn,
    FadeOut,
    Rectangle,
    Scene,
    Text,
    VGroup,
    config,
)

# Palette overridden by implementer per storyboard.meta.palette.
PALETTE = {
    "primary": "#4ADEDC",
    "accent":  "#8B5CF6",
    "warn":    "#F5E6C8",
    "bg":      "#0F1B2D",
}

_HEADER_HEIGHT = 0.6
_CAPTION_FONT_SIZE = 28
_CAPTION_FADE_S = 0.25


def add_header(scene: Scene, idx: int, total: int, title: str) -> VGroup:
    """Add a persistent top progress bar with title + scene N/total counter.

    No animation — added instantly via ``scene.add(...)``.
    Returns the VGroup for callers that want to tweak/remove it.
    """
    frame_w = config.frame_width
    bar = Rectangle(
        width=frame_w,
        height=_HEADER_HEIGHT,
        fill_color=PALETTE["bg"],
        fill_opacity=0.85,
        stroke_width=0,
    )
    # Anchor top edge so bar sits flush at the top of the frame.
    bar.to_edge(UP, buff=0.0)

    counter = Text(
        f"{idx:02d} / {total:02d}",
        font_size=22,
        color=PALETTE["primary"],
    )
    counter.next_to(bar.get_left(), RIGHT, buff=0.4).align_to(bar, UP).shift(DOWN * 0.3)

    title_text = Text(title, font_size=24, color=PALETTE["primary"])
    title_text.move_to(bar.get_center())

    # Progress fill — a narrower bar showing fraction complete.
    progress_w = frame_w * (idx / max(total, 1))
    progress = Rectangle(
        width=max(progress_w, 0.02),
        height=0.06,
        fill_color=PALETTE["accent"],
        fill_opacity=1.0,
        stroke_width=0,
    )
    progress.align_to(bar, DOWN).align_to(bar, LEFT)

    chrome = VGroup(bar, progress, counter, title_text)
    scene.add(chrome)
    return chrome


def add_title_card(scene: Scene, title: str, duration_s: float = 1.5) -> None:
    """Render a full-frame title card: FadeIn → hold → FadeOut, total ``duration_s``."""
    bg = Rectangle(
        width=config.frame_width,
        height=config.frame_height,
        fill_color=PALETTE["bg"],
        fill_opacity=0.95,
        stroke_width=0,
    ).move_to(ORIGIN)
    text = Text(title, font_size=56, color=PALETTE["primary"]).move_to(ORIGIN)
    card = VGroup(bg, text)
    fade = max(min(duration_s * 0.3, 0.6), 0.2)
    hold = max(duration_s - 2 * fade, 0.1)
    scene.play(FadeIn(card), run_time=fade)
    scene.wait(hold)
    scene.play(FadeOut(card), run_time=fade)


def chunk_captions(
    text: str,
    total_s: float,
    words_per_chunk: int = 10,
) -> list[tuple[str, float, float]]:
    """Split ``text`` into ≤``words_per_chunk`` groups; distribute across ``total_s``.

    Returns ``[(chunk_text, start_s, end_s), ...]``. Empty ``text`` returns ``[]``.
    Zero/negative ``total_s`` collapses to a single zero-duration chunk for safety.
    """
    words = (text or "").split()
    if not words:
        return []
    if total_s <= 0:
        return [(" ".join(words), 0.0, 0.0)]

    groups: list[list[str]] = []
    for i in range(0, len(words), max(words_per_chunk, 1)):
        groups.append(words[i : i + words_per_chunk])

    total_words = sum(len(g) for g in groups)
    out: list[tuple[str, float, float]] = []
    cursor = 0.0
    for g in groups:
        share = (len(g) / total_words) * total_s
        out.append((" ".join(g), cursor, cursor + share))
        cursor += share
    # Ensure last chunk lands exactly at total_s (avoid float drift).
    last_text, last_start, _ = out[-1]
    out[-1] = (last_text, last_start, total_s)
    return out


def attach_caption_track(
    scene: Scene,
    chunks: list[tuple[str, float, float]],
) -> Text | None:
    """Attach an updater-driven caption track that swaps text over elapsed time."""
    if not chunks:
        return None
    caption = Text("", font_size=_CAPTION_FONT_SIZE, color=PALETTE["warn"])
    caption.to_edge(DOWN, buff=0.5)
    caption.set_opacity(0)
    scene.add(caption)
    state = {"elapsed": 0.0, "active": -1}

    def updater(mob: Text, dt: float) -> None:
        state["elapsed"] += dt
        now = state["elapsed"]
        active = -1
        for i, (_t, start, end) in enumerate(chunks):
            if start <= now < end:
                active = i
                break
        if active == state["active"]:
            return
        state["active"] = active
        if active < 0:
            mob.set_opacity(0)
            return
        replacement = Text(
            chunks[active][0],
            font_size=_CAPTION_FONT_SIZE,
            color=PALETTE["warn"],
        ).to_edge(DOWN, buff=0.5)
        mob.become(replacement)
        mob.set_opacity(1)

    caption.add_updater(updater)
    return caption


def play_with_captions(
    scene: Scene,
    body_callable,
    voiceover_text: str,
    total_s: float,
    voice_enabled: bool,
    words_per_chunk: int = 10,
) -> None:
    """Run ``body_callable(scene, tracker)`` with caption track attached.

    When ``voice_enabled``: wraps body in ``scene.voiceover(...)``; tracker is the
    voiceover ``DurationTracker``. When False: tracker is ``None`` and total_s drives
    the caption clock alone.
    """
    chunks = chunk_captions(voiceover_text, total_s, words_per_chunk)
    if voice_enabled:
        # VoiceoverScene API; importer must use VoiceoverScene as base class.
        with scene.voiceover(text=voiceover_text) as tracker:  # type: ignore[attr-defined]
            track = attach_caption_track(scene, chunks)
            body_callable(scene, tracker)
            if track is not None:
                track.clear_updaters()
    else:
        track = attach_caption_track(scene, chunks)
        body_callable(scene, None)
        if track is not None:
            track.clear_updaters()
