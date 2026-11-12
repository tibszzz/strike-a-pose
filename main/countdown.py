"""Countdown timer settings and fade (Strike's round timer, reused by Dodgeball).

One large, centred, outlined, translucent digit; each new digit blinks off for
a moment, then fades in. Drawn by `main.games.strike.game.draw_countdown_timer`.
"""

from __future__ import annotations


TIMER_OPACITY = 0.65
TIMER_CENTER_SCALE = 16.0
TIMER_VISIBLE_AT_SECONDS = 3  # digits above this stay hidden
TIMER_BLINK_SECONDS = 0.06
TIMER_FADE_SECONDS = 0.28


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
