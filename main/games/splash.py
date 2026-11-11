"""Boot splash before the in-window menu. Thumbs up advances."""

from __future__ import annotations

import pygame

from main.nav import GestureSnapshot, MenuCommand, Nav, QuitApp, StartGame
from main.pose import PoseFrame

WHITE = (255, 255, 255)
MUTED = (180, 180, 180)
ACCENT = (255, 220, 80)
HAND_BOX = (80, 220, 255)

PLACEHOLDER_TITLE = "Strike a Pose"


class SplashGame:
    title = PLACEHOLDER_TITLE
    is_splash = True
    wants_gestures = True
    background = (0, 0, 0)

    def __init__(self, size: tuple[int, int]) -> None:
        self.w, self.h = size
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        self._title_font = pygame.font.SysFont("menlo,monaco,courier", max(36, self.h // 12), bold=True)
        self._hint_font = pygame.font.SysFont("menlo,monaco,courier", max(16, self.h // 28))

    def reset(self) -> None:
        self._pending = None

    def update(self, frame: PoseFrame) -> None:
        self._frame = frame

    def render_camera(self, image):
        return image

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        snap = self.gesture_snapshot

        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        canvas.blit(overlay, (0, 0))

        if snap is not None and snap.hand_box is not None:
            x1, y1, x2, y2 = snap.hand_box
            pygame.draw.rect(
                canvas,
                HAND_BOX,
                pygame.Rect(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                width=3,
            )

        title = self._title_font.render(PLACEHOLDER_TITLE, True, WHITE)
        title_y = self.h // 2 - title.get_height()
        canvas.blit(title, (self.w // 2 - title.get_width() // 2, title_y))

        prompt = self._hint_font.render("Thumbs up to start", True, ACCENT)
        canvas.blit(
            prompt,
            (self.w // 2 - prompt.get_width() // 2, title_y + title.get_height() + 16),
        )

        status_y = title_y + title.get_height() + 16 + prompt.get_height() + 20
        if snap is not None and snap.label:
            status = self._hint_font.render(f"{snap.label}  {snap.score:.2f}", True, WHITE)
        else:
            status = self._hint_font.render("show a thumbs up…", True, MUTED)
        canvas.blit(status, (self.w // 2 - status.get_width() // 2, status_y))

    def handle_command(self, command: MenuCommand) -> None:
        if command is MenuCommand.MOVE_UP or command is MenuCommand.SELECT:
            self._pending = StartGame(None)
        elif command is MenuCommand.BACK:
            self._pending = QuitApp()

    def poll_nav(self) -> Nav | None:
        nav = self._pending
        self._pending = None
        return nav

    def debug_lines(self) -> list[str]:
        snap = self.gesture_snapshot
        label = snap.label if snap and snap.label else "-"
        return ["splash", f"gesture {label}"]
