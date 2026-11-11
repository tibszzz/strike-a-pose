"""Boot splash before the in-window menu. Hold Thumb_Up to advance."""

from __future__ import annotations

import pygame

from main import content, styles
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

theme = styles.BRAND  # full-bleed splash overlay (alpha 160)
copy = content.Shell


class SplashGame:
    title = copy.brand
    is_splash = True
    wants_gestures = True
    background = theme.bg

    def __init__(self, size: tuple[int, int]) -> None:
        self.w, self.h = size
        self._pending: Nav | None = None
        self._frame: PoseFrame | None = None
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(hold_s=cfg.thumb_hold_s, min_score=cfg.min_score)
        self._title_font = styles.load_font(theme.title, theme.title_px(self.h))
        self._hint_font = styles.load_font(theme.body, theme.body_px(self.h))

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
        overlay.fill(theme.overlay)
        canvas.blit(overlay, (0, 0))

        if snap is not None and snap.hand_box is not None:
            x1, y1, x2, y2 = snap.hand_box
            pygame.draw.rect(
                canvas,
                theme.hand_box,
                pygame.Rect(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                width=3,
            )

        title = self._title_font.render(copy.brand, True, theme.ink)
        title_y = self.h // 2 - title.get_height()
        canvas.blit(title, (self.w // 2 - title.get_width() // 2, title_y))

        prompt = self._hint_font.render(copy.splash_prompt, True, theme.accent)
        prompt_y = title_y + title.get_height() + 16
        canvas.blit(prompt, (self.w // 2 - prompt.get_width() // 2, prompt_y))

        bar_w = min(self.w // 3, 280)
        bar_h = max(8, self.h // 80)
        bar_x = self.w // 2 - bar_w // 2
        bar_y = prompt_y + prompt.get_height() + 18
        track = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        track.fill(theme.hold_track)
        canvas.blit(track, (bar_x, bar_y))
        if self._thumb.progress > 0:
            fill_w = max(1, int(bar_w * self._thumb.progress))
            fill = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            fill.fill(theme.hold_fill)
            canvas.blit(fill, (bar_x, bar_y))

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
