"""In-process game picker. Implements the shared Game protocol.

Tile grid: index fingertip over a tile hard-locks it (follows while you
move), Closed_Fist held confirms. While a Closed_Fist hold is in progress,
selection does not switch and a different hand's Closed_Fist is ignored until
the confirming hand drops the gesture. Shell keyboard (`--debug`) moves
hard-lock and confirms instantly; gestures are handled here from
`gesture_snapshot`, not via shell MenuCommand mapping.
"""

from __future__ import annotations

from typing import Sequence

import pygame

from main import content, styles
from main.games.registry import GameEntry
from main.nav import (
    GestureSnapshot,
    MenuCommand,
    Nav,
    QuitApp,
    StartGame,
    ThumbHoldTracker,
    load_gesture_nav_config,
)
from main.nav.hand_draw import draw_primary_hand_hold
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import PoseFrame

theme = styles.SHELL
copy = content.Shell

# MediaPipe hand landmark index for index fingertip.
INDEX_FINGERTIP = 8


class MenuGame:
    title = copy.brand
    is_menu = True
    wants_gestures = True
    gesture_hands = NAV_GESTURE_HANDS
    background = theme.bg

    def __init__(self, size: tuple[int, int], entries: Sequence[GameEntry]) -> None:
        if not entries:
            raise ValueError("menu needs at least one playable game")
        self.w, self.h = size
        self.entries = tuple(entries)
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(
            hold_s=cfg.thumb_hold_s,
            min_score=cfg.min_score,
            label="Closed_Fist",
        )
        self._hard_lock: int | None = None
        self._hover: int | None = None
        self._title_font = styles.load_font(theme.font, theme.menu_title_px(self.h))
        self._hint_font = styles.load_font(theme.font, theme.hint_px(self.h))
        self._tile_label_font = styles.load_font(theme.font, theme.tile_label_px(self.h))

    def reset(self) -> None:
        self._pending = None
        self._hard_lock = None
        self._hover = None
        self._thumb.reset()

    def _title_y(self) -> int:
        return self.h // 10

    def _hint_y(self) -> int:
        bottom_margin = max(16, self.h // 36)
        return self.h - self._hint_font.get_height() - bottom_margin

    def tile_rects(self) -> list[pygame.Rect]:
        n = len(self.entries)
        margin_x = self.w * 0.08
        gap = self.w * 0.04
        available = self.w - 2 * margin_x - (n - 1) * gap
        title_bottom = self._title_y() + self._title_font.get_height()
        hint_top = self._hint_y()
        band_pad = max(12, self.h // 48)
        band_top = title_bottom + band_pad
        band_h = max(1, hint_top - band_pad - band_top)
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

    def update(self, frame: PoseFrame) -> None:
        self._frame = frame
        snap = self.gesture_snapshot
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
            frame.timestamp,
            frame_size=(self.w, self.h),
            armed=self._hard_lock is not None,
        ):
            assert self._hard_lock is not None
            self._pending = StartGame(self.entries[self._hard_lock].id)

    def render_camera(self, image):
        return image

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        snap = self.gesture_snapshot

        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill(theme.overlay)
        canvas.blit(overlay, (0, 0))

        title = self._title_font.render(copy.menu_title, True, theme.ink)
        canvas.blit(title, (self.w // 2 - title.get_width() // 2, self._title_y()))

        for i, (entry, rect) in enumerate(zip(self.entries, self.tile_rects())):
            fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            fill.fill(theme.tile_fill)
            canvas.blit(fill, rect.topleft)

            locked = i == self._hard_lock
            hovered = i == self._hover
            if locked:
                border_color = theme.accent
                border_w = 5
                name_color = theme.accent
            elif hovered:
                border_color = theme.hover
                border_w = 3
                name_color = theme.ink
            else:
                border_color = theme.muted
                border_w = 2
                name_color = theme.ink

            pygame.draw.rect(canvas, border_color, rect, width=border_w)

            label = self._tile_label_font.render(entry.label, True, name_color)
            canvas.blit(
                label,
                (
                    rect.centerx - label.get_width() // 2,
                    rect.centery - label.get_height() // 2,
                ),
            )

        primary = self._hint_font.render(copy.menu_hint, True, theme.ink)
        styles.apply_hint_blink(primary, frame.timestamp)
        canvas.blit(primary, (self.w // 2 - primary.get_width() // 2, self._hint_y()))

        # Hand chrome last so the skeleton/ring sit above tiles and copy.
        draw_primary_hand_hold(
            canvas, snap, self._thumb.progress, color=theme.accent
        )

    def handle_command(self, command: MenuCommand) -> None:
        n = len(self.entries)
        if command is MenuCommand.MOVE_UP:
            self._set_hard_lock(n - 1 if self._hard_lock is None else (self._hard_lock - 1) % n)
        elif command is MenuCommand.MOVE_DOWN:
            self._set_hard_lock(0 if self._hard_lock is None else (self._hard_lock + 1) % n)
        elif command is MenuCommand.SELECT:
            if self._hard_lock is not None:
                self._pending = StartGame(self.entries[self._hard_lock].id)
        elif command is MenuCommand.BACK:
            self._pending = QuitApp()

    def poll_nav(self) -> Nav | None:
        nav = self._pending
        self._pending = None
        return nav

    def debug_lines(self) -> list[str]:
        snap = self.gesture_snapshot
        label = snap.label if snap and snap.label else "-"
        locked = self.entries[self._hard_lock].id if self._hard_lock is not None else "-"
        return [f"menu lock {locked}", f"gesture {label}"]

    def _set_hard_lock(self, index: int) -> None:
        if self._hard_lock != index:
            self._hard_lock = index
            self._thumb.reset()


def _index_tip(snap: GestureSnapshot | None) -> tuple[float, float] | None:
    if snap is None or len(snap.landmarks) <= INDEX_FINGERTIP:
        return None
    return snap.landmarks[INDEX_FINGERTIP]
