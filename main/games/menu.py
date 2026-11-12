"""In-process game picker. Implements the shared Game protocol.

Live camera behind a row of notebook-page buttons across the top (one per
game, then Quit), the brand title bottom-right and faint gesture hints
bottom-left. Hovering a note (index fingertip) selects it and the selection
sticks after the hand moves away; Closed_Fist held anywhere presses the
selected note. While a Closed_Fist hold is in
progress, selection does not switch and a different hand's Closed_Fist is
ignored until the confirming hand drops the gesture. Shell keyboard
(`--debug`) moves hard-lock and confirms instantly; gestures are handled here
from `gesture_snapshot`, not via shell MenuCommand mapping.

`release_first`: when the menu is reached by a fist confirm elsewhere, the
still-closed hand must open once before a new hold can count.
"""

from __future__ import annotations

from typing import Sequence

import pygame

from main import content
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
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import PoseFrame
from main.ui import paper, widgets
from main.ui.paper import Frame
from main.ui.widgets import INDEX_FINGERTIP, Hint

copy = content.Shell
hints = content.Hints

QUIT_ID = "quit"

__all__ = ["INDEX_FINGERTIP", "MenuGame", "QUIT_ID"]


class MenuGame:
    title = copy.brand
    is_menu = True
    wants_gestures = True
    gesture_hands = NAV_GESTURE_HANDS
    background = paper.BACKDROP

    def __init__(
        self,
        size: tuple[int, int],
        entries: Sequence[GameEntry],
        *,
        release_first: bool = False,
    ) -> None:
        if not entries:
            raise ValueError("menu needs at least one playable game")
        self.w, self.h = size
        self.frame = Frame(self.w, self.h)
        self.entries = tuple(entries)
        self._labels = tuple(e.label for e in self.entries) + (copy.menu_quit,)
        self._ids = tuple(e.id for e in self.entries) + (QUIT_ID,)
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._min_score = cfg.min_score
        self._thumb = ThumbHoldTracker(
            hold_s=cfg.thumb_hold_s,
            min_score=cfg.min_score,
            label="Closed_Fist",
        )
        self._release_first = release_first
        self._released = not release_first
        self._hard_lock: int | None = None
        self._hover: int | None = None

    def reset(self) -> None:
        self._pending = None
        self._hard_lock = None
        self._hover = None
        self._released = not self._release_first
        self._thumb.reset()

    def tile_rects(self) -> list[pygame.Rect]:
        return widgets.note_row_rects(self.frame, self._labels)

    def update(self, frame: PoseFrame) -> None:
        self._frame = frame
        snap = self.gesture_snapshot
        if not self._released and effective_label(snap, self._min_score) != "Closed_Fist":
            self._released = True
        tip = widgets.pointer(snap)
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
            armed=self._hard_lock is not None and self._released,
        ):
            assert self._hard_lock is not None
            self._pending = self._nav_for(self._hard_lock)

    def render_camera(self, image):
        return image

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        f = self.frame
        paper.shade_video(canvas)

        for i, (label, rect) in enumerate(zip(self._labels, self.tile_rects())):
            locked = i == self._hard_lock
            widgets.draw_note_button(
                canvas,
                f,
                rect,
                i + 1,
                label,
                selected=locked,
                seed=100 + i,
                progress=self._thumb.progress if locked else 0.0,
            )

        # Gesture hints: small and faded, bottom-left; brand title bottom-right.
        widgets.draw_hint_bar(
            canvas,
            f,
            f.rect(50, 770, 610, 846),
            (
                Hint(widgets.PALM_ICON, hints.hover_heading, hints.hover_sub),
                Hint(widgets.FIST_ICON, hints.select_heading, hints.start_sub),
            ),
            scale=0.68,
            alpha=150,
        )
        widgets.draw_title_strip(
            canvas,
            f,
            copy.menu_title,
            x=1492,
            y=842,
            size=104,
            seed=7,
            condense=0.74,
            anchor="bottomright",
        )

        # Pointer last so it sits above the notes.
        widgets.draw_cursor(canvas, f, self.gesture_snapshot, self._thumb.progress)

    def handle_command(self, command: MenuCommand) -> None:
        n = len(self._labels)
        if command is MenuCommand.MOVE_UP:
            self._set_hard_lock(n - 1 if self._hard_lock is None else (self._hard_lock - 1) % n)
        elif command is MenuCommand.MOVE_DOWN:
            self._set_hard_lock(0 if self._hard_lock is None else (self._hard_lock + 1) % n)
        elif command is MenuCommand.SELECT:
            if self._hard_lock is not None:
                self._pending = self._nav_for(self._hard_lock)
        elif command is MenuCommand.BACK:
            self._pending = QuitApp()

    def poll_nav(self) -> Nav | None:
        nav = self._pending
        self._pending = None
        return nav

    def debug_lines(self) -> list[str]:
        snap = self.gesture_snapshot
        label = snap.label if snap and snap.label else "-"
        locked = self._ids[self._hard_lock] if self._hard_lock is not None else "-"
        return [f"menu lock {locked}", f"gesture {label}"]

    def _nav_for(self, index: int) -> Nav:
        if self._ids[index] == QUIT_ID:
            return QuitApp()
        return StartGame(self._ids[index])

    def _set_hard_lock(self, index: int) -> None:
        if self._hard_lock != index:
            self._hard_lock = index
            self._thumb.reset()
