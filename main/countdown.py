"""Shared big-digit countdown look (Strike's round timer, reused by Dodgeball).

One large, centred, outlined, translucent digit. Each new digit blinks off for
a moment, then fades in. Sizes are design scales at the canvas height, so the
digit looks the same on any canvas size.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from main import styles

TIMER_OPACITY = 0.65
TIMER_CENTER_SCALE = 16.0
TIMER_VISIBLE_AT_SECONDS = 3  # digits above this stay hidden
TIMER_BLINK_SECONDS = 0.06
TIMER_FADE_SECONDS = 0.28
TIMER_COLOR = (255, 255, 255)  # RGB


def ease_out(t: float) -> float:
    """Cubic ease-out for t in [0, 1]."""
    u = 1.0 - t
    return 1.0 - u * u * u


def timer_opacity(seconds_left: int, digit_age: float) -> float | None:
    """None while hidden (above 3, or at 0); else the digit's current opacity.

    `digit_age` is how long (s) the current digit has been showing.
    """
    if seconds_left > TIMER_VISIBLE_AT_SECONDS or seconds_left <= 0:
        return None
    if digit_age < TIMER_BLINK_SECONDS:
        return 0.0
    fade_t = (digit_age - TIMER_BLINK_SECONDS) / TIMER_FADE_SECONDS
    if fade_t >= 1.0:
        return TIMER_OPACITY
    return TIMER_OPACITY * ease_out(max(0.0, min(1.0, fade_t)))


def baseline_for_vertical_center(
    text: str, center_y: int, scale: float, face: Path | None, h: int
) -> int:
    """Baseline that places the glyph's visual centre at `center_y`."""
    (_, height), descent = styles.text_size(text, scale, face, h=h)
    return round(center_y + (height - descent) / 2)


def draw_countdown_digit(
    canvas: pygame.Surface,
    seconds_left: int,
    digit_age: float,
    *,
    face: Path | None = None,
    color: tuple[int, int, int] = TIMER_COLOR,
) -> None:
    """Draw the countdown digit centred on a pygame canvas (no-op while hidden)."""
    opacity = timer_opacity(seconds_left, digit_age)
    if opacity is None or opacity <= 0:
        return
    w, h = canvas.get_size()
    text = str(seconds_left)
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    baseline = baseline_for_vertical_center(text, h // 2, TIMER_CENTER_SCALE, face, h)
    styles.draw_text(
        layer, text, w // 2, baseline, TIMER_CENTER_SCALE, color,
        align="center", outline=True, face=face, h=h,
    )
    layer.set_alpha(round(255 * opacity))
    canvas.blit(layer, (0, 0))
