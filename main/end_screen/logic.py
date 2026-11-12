"""Two-tile Replay / Menu chooser: tip hard-lock + Closed_Fist confirm.

Mirrors MenuGame interaction: index fingertip over a tile hard-locks it
(follows while you move); Closed_Fist held confirms. While a fist hold is
in progress, selection does not switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from main.nav import GestureSnapshot, MenuCommand, ThumbHoldTracker, load_gesture_nav_config

# MediaPipe hand landmark index for index fingertip.
INDEX_FINGERTIP = 8


class EndChoice(Enum):
    REPLAY = auto()
    MENU = auto()


@dataclass(frozen=True)
class EndScreenConfig:
    hold_s: float | None = None
    min_score: float | None = None


class EndScreen:
    """Pure chooser state. Call `update` with a gesture snapshot each frame."""

    OPTIONS: tuple[EndChoice, ...] = (EndChoice.REPLAY, EndChoice.MENU)

    def __init__(self, size: tuple[int, int], config: EndScreenConfig | None = None) -> None:
        self.w, self.h = size
        cfg = config or EndScreenConfig()
        nav = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(
            hold_s=cfg.hold_s if cfg.hold_s is not None else nav.thumb_hold_s,
            min_score=cfg.min_score if cfg.min_score is not None else nav.min_score,
            label="Closed_Fist",
        )
        self._hard_lock: int | None = None
        self._hover: int | None = None
        self._choice: EndChoice | None = None

    @property
    def hard_lock(self) -> int | None:
        return self._hard_lock

    @property
    def hover(self) -> int | None:
        return self._hover

    @property
    def hold_progress(self) -> float:
        return self._thumb.progress

    @property
    def thumb(self) -> ThumbHoldTracker:
        return self._thumb

    def reset(self) -> None:
        self._hard_lock = None
        self._hover = None
        self._choice = None
        self._thumb.reset()

    def tile_rects(self) -> list[pygame.Rect]:
        n = len(self.OPTIONS)
        margin_x = self.w * 0.12
        gap = self.w * 0.05
        available = self.w - 2 * margin_x - (n - 1) * gap
        # Center band below a winner headline / above the hint.
        band_top = int(self.h * 0.42)
        band_bottom = int(self.h * 0.82)
        band_h = max(1, band_bottom - band_top)
        side = min(available / n, band_h)
        total_w = n * side + (n - 1) * gap
        start_x = (self.w - total_w) / 2
        top = band_top + (band_h - side) / 2
        return [
            pygame.Rect(
                int(start_x + i * (side + gap)),
                int(top),
                int(side),
                int(side),
            )
            for i in range(n)
        ]

    def update(
        self,
        snap: GestureSnapshot | None,
        timestamp: float,
    ) -> EndChoice | None:
        """Advance selection; return a choice once when fist hold completes."""
        tip = _index_tip(snap)
        rects = self.tile_rects()

        self._hover = None
        if tip is not None:
            for i, rect in enumerate(rects):
                if rect.collidepoint(tip):
                    self._hover = i
                    break

        if self._hover is not None and not self._thumb.active:
            if self._hard_lock != self._hover:
                self._hard_lock = self._hover
                self._thumb.reset()

        if self._thumb.update(
            snap,
            timestamp,
            frame_size=(self.w, self.h),
            armed=self._hard_lock is not None,
        ):
            assert self._hard_lock is not None
            choice = self.OPTIONS[self._hard_lock]
            self._choice = choice
            return choice
        return None

    def handle_command(self, command: MenuCommand) -> EndChoice | None:
        """Debug keyboard: arrows move lock, SELECT confirms instantly."""
        n = len(self.OPTIONS)
        if command is MenuCommand.MOVE_UP:
            self._set_hard_lock(n - 1 if self._hard_lock is None else (self._hard_lock - 1) % n)
        elif command is MenuCommand.MOVE_DOWN:
            self._set_hard_lock(0 if self._hard_lock is None else (self._hard_lock + 1) % n)
        elif command is MenuCommand.SELECT:
            if self._hard_lock is not None:
                choice = self.OPTIONS[self._hard_lock]
                self._choice = choice
                return choice
        return None

    def _set_hard_lock(self, index: int) -> None:
        if self._hard_lock != index:
            self._hard_lock = index
            self._thumb.reset()


def _index_tip(snap: GestureSnapshot | None) -> tuple[float, float] | None:
    if snap is None or len(snap.landmarks) <= INDEX_FINGERTIP:
        return None
    return snap.landmarks[INDEX_FINGERTIP]
