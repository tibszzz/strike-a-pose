"""Tunable settings for Dodgeball."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DodgeballConfig:
    min_players: int = 1
    max_players: int = 3
    fps: int = 30
    lives: int = 5  # chances per player; at 0 the player is out
    offscreen_seconds: float = 3.0  # out of frame this long during play = lose a life

    @property
    def offscreen_frames(self) -> int:
        return int(self.offscreen_seconds * self.fps)

    @property
    def gesture_hold_frames(self) -> int:
        # Hold a thumb this long (~0.3s at 30fps) for it to count.
        return max(1, self.fps // 3)
