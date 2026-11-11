"""Boot splash before the in-window menu. Hold Thumb_Up to advance."""

from __future__ import annotations

import pygame

from main.nav import (
    GestureSnapshot,
    MenuCommand,
    Nav,
    QuitApp,
    StartGame,
    ThumbHoldTracker,
    load_gesture_nav_config,
)
from main.pose import PoseFrame

WHITE = (255, 255, 255)
MUTED = (180, 180, 180)
ACCENT = (255, 220, 80)
HAND_BOX = (80, 220, 255)
HOLD_TRACK = (255, 255, 255, 40)
HOLD_FILL = (255, 220, 80, 200)

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
        cfg = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(hold_s=cfg.thumb_hold_s, min_score=cfg.min_score)
        self._title_font = pygame.font.SysFont("menlo,monaco,courier", max(36, self.h // 12), bold=True)
        self._hint_font = pygame.font.SysFont("menlo,monaco,courier", max(16, self.h // 28))

    def reset(self) -> None:
        self._pending = None
        self._thumb.reset()

    def update(self, frame: PoseFrame) -> None:
        self._frame = frame
        if self._thumb.update(
            self.gesture_snapshot,
            frame.timestamp,
            frame_size=(self.w, self.h),
        ):
            self._pending = StartGame(None)

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

        prompt = self._hint_font.render("Hold thumbs up to start", True, ACCENT)
        prompt_y = title_y + title.get_height() + 16
        canvas.blit(prompt, (self.w // 2 - prompt.get_width() // 2, prompt_y))

        bar_w = min(self.w // 3, 280)
        bar_h = max(8, self.h // 80)
        bar_x = self.w // 2 - bar_w // 2
        bar_y = prompt_y + prompt.get_height() + 18
        track = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        track.fill(HOLD_TRACK)
        canvas.blit(track, (bar_x, bar_y))
        if self._thumb.progress > 0:
            fill_w = max(1, int(bar_w * self._thumb.progress))
            fill = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            fill.fill(HOLD_FILL)
            canvas.blit(fill, (bar_x, bar_y))

        status_y = bar_y + bar_h + 16
        hold = self._thumb.hold_status()
        if hold is not None:
            status = self._hint_font.render(hold, True, ACCENT)
        elif snap is not None and snap.label:
            status = self._hint_font.render(f"{snap.label}  {snap.score:.2f}", True, WHITE)
        else:
            status = self._hint_font.render("show a thumbs up…", True, MUTED)
        canvas.blit(status, (self.w // 2 - status.get_width() // 2, status_y))

    def handle_command(self, command: MenuCommand) -> None:
        # Keyboard (--debug): Enter / arrows still advance instantly.
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
