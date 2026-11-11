"""Tunable settings for Wild West Duel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DuelConfig:
    lives: int = 3  # hits a player can take; the last one loses the match
    start_hold: float = 1.0  # both visible and not drawing this long to start a round
    ready_to_steady: float = 1.5
    bang_delay_min: float = 1.5  # STEADY -> BANG, uniform random
    bang_delay_max: float = 5.0
    draw_timeout: float = 3.0  # after BANG, no valid draw in this time -> no point
    tie_window: float = 0.034  # draws this close (about 1 frame at 30 fps) are a tie
    settle_time: float = 0.15  # after first draw, wait this long for a possible tie
    draw_confirm_frames: int = 2
    round_result_time: float = 3.0  # how long the round result is shown
    match_result_min_time: float = 3.0  # winner screen shown at least this long (after the round result)
    # Solo testing: the empty half is treated as an idle ghost so one person can play.
    debug: bool = False


@dataclass(frozen=True)
class ViewConfig:
    early_float_time: float = 2.0  # seconds for "too early" to drift up the path and vanish
    early_fade_start: float = 0.5  # fraction of the trip after which it starts fading


@dataclass(frozen=True)
class GestureConfig:
    min_conf: float = 0.5
    # Elbow angle in degrees (180 = perfectly straight) needed to count as extended.
    min_elbow_angle: float = 140.0
    # Max angle of the shoulder->wrist line away from horizontal, in degrees.
    max_arm_tilt: float = 30.0
