"""In-process game picker. Implements the shared Game protocol."""

from __future__ import annotations

from typing import Sequence

import pygame

from main.games.registry import GameEntry
from main.nav import GestureSnapshot, MenuCommand, Nav, QuitApp, StartGame
from main.pose import PoseFrame

WHITE = (255, 255, 255)
INK = (20, 20, 20)
MUTED = (180, 180, 180)
ACCENT = (255, 220, 80)
HAND_BOX = (80, 220, 255)


class MenuGame:
    title = "CIID Play Party"
    is_menu = True
    wants_gestures = True
    background = (0, 0, 0)

    def __init__(self, size: tuple[int, int], entries: Sequence[GameEntry]) -> None:
        if not entries:
            raise ValueError("menu needs at least one playable game")
        self.w, self.h = size
        self.entries = tuple(entries)
        self.index = 0
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        self._font = pygame.font.SysFont("menlo,monaco,courier", max(18, self.h // 28))
        self._title_font = pygame.font.SysFont("menlo,monaco,courier", max(28, self.h // 16), bold=True)
        self._hint_font = pygame.font.SysFont("menlo,monaco,courier", max(14, self.h // 36))

    def reset(self) -> None:
        self.index = 0
        self._pending = None

    def update(self, frame: PoseFrame) -> None:
        self._frame = frame

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

        title = self._title_font.render("CIID Play Party", True, WHITE)
        canvas.blit(title, (self.w // 2 - title.get_width() // 2, self.h // 10))

        hint_y = self.h // 10 + title.get_height() + 8
        primary = self._hint_font.render(
            "Thumbs up/down move  ·  Victory selects",
            True,
            ACCENT,
        )
        canvas.blit(primary, (self.w // 2 - primary.get_width() // 2, hint_y))
        secondary = self._hint_font.render(
            "Keys: Up/Down  Enter  ·  Esc quit",
            True,
            MUTED,
        )
        canvas.blit(secondary, (self.w // 2 - secondary.get_width() // 2, hint_y + primary.get_height() + 4))

        status_y = hint_y + primary.get_height() + secondary.get_height() + 12
        if snap is not None and snap.label:
            status = self._hint_font.render(f"{snap.label}  {snap.score:.2f}", True, WHITE)
        else:
            status = self._hint_font.render("show a hand gesture…", True, MUTED)
        canvas.blit(status, (self.w // 2 - status.get_width() // 2, status_y))

        top = self.h // 3
        line_h = max(36, self.h // 14)
        for i, entry in enumerate(self.entries):
            selected = i == self.index
            label = f"{'> ' if selected else '  '}{entry.label}"
            color = ACCENT if selected else WHITE
            text = self._font.render(label, True, color)
            canvas.blit(text, (self.w // 2 - text.get_width() // 2, top + i * line_h))

    def handle_command(self, command: MenuCommand) -> None:
        if command is MenuCommand.MOVE_UP:
            self.index = (self.index - 1) % len(self.entries)
        elif command is MenuCommand.MOVE_DOWN:
            self.index = (self.index + 1) % len(self.entries)
        elif command is MenuCommand.SELECT:
            self._pending = StartGame(self.entries[self.index].id)
        elif command is MenuCommand.BACK:
            self._pending = QuitApp()

    def poll_nav(self) -> Nav | None:
        nav = self._pending
        self._pending = None
        return nav

    def debug_lines(self) -> list[str]:
        snap = self.gesture_snapshot
        label = snap.label if snap and snap.label else "-"
        return [f"menu {self.entries[self.index].id}", f"gesture {label}"]
