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
    replay_speed: float = 0.25  # slow-mo factor for post-hit action replay (1.0 = realtime)
    replay_freeze: float = 1.0  # seconds to hold the impact frame after slow-mo
    # Solo testing: the empty half is treated as an idle ghost so one person can play.
    debug: bool = False


@dataclass(frozen=True)
class ViewConfig:
    early_float_time: float = 3.2  # seconds for "too early" to drift up the path and vanish
    early_fade_start: float = 0.5  # fraction of the trip after which it starts fading
    # Side camera PiPs: body framing windows under the name/hearts band.
    preview_width: float = 0.20  # fraction of canvas width
    preview_height: float = 0.50  # fraction of canvas height
    preview_top: float = 0.24  # fraction of canvas height; clears the hearts
    preview_margin_x: float = 0.1  # fraction of canvas width from the outer edge
    preview_pad: float = 0.18  # pad around Person.box before aspect expand
    preview_smooth: float = 0.35  # EMA alpha toward the latest crop (higher = snappier)
    preview_grace: float = 0.3  # seconds to hold last crop after track loss
    replay_scale: float = 0.5  # linear downscale for bang→draw frame buffer


@dataclass(frozen=True)
class GestureConfig:
    min_conf: float = 0.5
    # Elbow angle in degrees (180 = perfectly straight) needed to count as extended.
    min_elbow_angle: float = 140.0
    # Max angle of the shoulder->wrist line away from horizontal, in degrees.
    max_arm_tilt: float = 30.0
