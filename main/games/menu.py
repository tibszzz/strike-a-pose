"""In-process game picker. Implements the shared Game protocol.

Tile grid: tip soft-hover, Pointing_Up sets hard-lock under the fingertip
(updates while you move), Thumb_Up held confirms. While a Thumb_Up hold is
in progress, a different hand's Thumb_Up is ignored until the confirming
hand drops the gesture. Shell keyboard (`--debug`) moves hard-lock and
confirms instantly; gestures are handled here from `gesture_snapshot`, not
via shell MenuCommand mapping.
"""

from __future__ import annotations

from typing import Sequence

import pygame

from main.games.registry import GameEntry
from main.nav import (
    GestureSnapshot,
    MenuCommand,
    Nav,
    QuitApp,
    StartGame,
    ThumbHoldTracker,
    effective_label,
    load_gesture_nav_config,
)
from main.pose import PoseFrame

WHITE = (255, 255, 255)
MUTED = (180, 180, 180)
ACCENT = (255, 220, 80)
HOVER = (220, 220, 220)
HAND_BOX = (80, 220, 255)
TILE_FILL = (0, 0, 0, 120)
HOLD_FILL = (255, 220, 80, 70)

# MediaPipe hand landmark index for index fingertip.
INDEX_FINGERTIP = 8


class MenuGame:
    title = "Strike a Pose"
    is_menu = True
    wants_gestures = True
    background = (0, 0, 0)

    def __init__(self, size: tuple[int, int], entries: Sequence[GameEntry]) -> None:
        if not entries:
            raise ValueError("menu needs at least one playable game")
        self.w, self.h = size
        self.entries = tuple(entries)
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(hold_s=cfg.thumb_hold_s, min_score=cfg.min_score)
        self._hard_lock: int | None = None
        self._hover: int | None = None
        self._font = pygame.font.SysFont("menlo,monaco,courier", max(18, self.h // 28))
        self._title_font = pygame.font.SysFont("menlo,monaco,courier", max(28, self.h // 16), bold=True)
        self._hint_font = pygame.font.SysFont("menlo,monaco,courier", max(14, self.h // 36))
        self._tile_label_font = pygame.font.SysFont(
            "menlo,monaco,courier", max(16, self.h // 32), bold=True
        )

    def reset(self) -> None:
        self._pending = None
        self._hard_lock = None
        self._hover = None
        self._thumb.reset()

    def tile_rects(self) -> list[pygame.Rect]:
        n = len(self.entries)
        margin_x = self.w * 0.08
        gap = self.w * 0.04
        available = self.w - 2 * margin_x - (n - 1) * gap
        side = min(available / n, self.h * 0.42)
        total_w = n * side + (n - 1) * gap
        start_x = (self.w - total_w) / 2
        top = self.h * 0.38
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

        label = effective_label(snap, self._thumb.min_score)

        if label == "Pointing_Up" and self._hover is not None and not self._thumb.active:
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
        overlay.fill((0, 0, 0, 140))
        canvas.blit(overlay, (0, 0))

        if snap is not None and snap.hand_box is not None:
            x1, y1, x2, y2 = snap.hand_box
            pygame.draw.rect(
                canvas,
                HAND_BOX,
                pygame.Rect(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                width=3,
            )

        title = self._title_font.render("Strike a Pose", True, WHITE)
        canvas.blit(title, (self.w // 2 - title.get_width() // 2, self.h // 10))

        hint_y = self.h // 10 + title.get_height() + 8
        primary = self._hint_font.render(
            "Pointing up selects · Hold thumbs up to start",
            True,
            ACCENT,
        )
        canvas.blit(primary, (self.w // 2 - primary.get_width() // 2, hint_y))

        status_y = hint_y + primary.get_height() + 12
        hold = self._thumb.hold_status()
        if hold is not None:
            status = self._hint_font.render(hold, True, ACCENT)
        elif snap is not None and snap.label:
            status = self._hint_font.render(f"{snap.label}  {snap.score:.2f}", True, WHITE)
        else:
            status = self._hint_font.render("show a hand gesture…", True, MUTED)
        canvas.blit(status, (self.w // 2 - status.get_width() // 2, status_y))

        for i, (entry, rect) in enumerate(zip(self.entries, self.tile_rects())):
            fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            fill.fill(TILE_FILL)
            canvas.blit(fill, rect.topleft)

            locked = i == self._hard_lock
            hovered = i == self._hover
            if locked and self._thumb.progress > 0:
                hold_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                hold_h = max(1, int(rect.height * self._thumb.progress))
                hold_surf.fill(HOLD_FILL)
                canvas.blit(
                    hold_surf,
                    (rect.left, rect.bottom - hold_h),
                    area=pygame.Rect(0, rect.height - hold_h, rect.width, hold_h),
                )

            if locked:
                border_color = ACCENT
                border_w = 5
                name_color = ACCENT
            elif hovered:
                border_color = HOVER
                border_w = 3
                name_color = WHITE
            else:
                border_color = MUTED
                border_w = 2
                name_color = WHITE

            pygame.draw.rect(canvas, border_color, rect, width=border_w)

            label = self._tile_label_font.render(entry.label, True, name_color)
            canvas.blit(
                label,
                (
                    rect.centerx - label.get_width() // 2,
                    rect.centery - label.get_height() // 2,
                ),
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
