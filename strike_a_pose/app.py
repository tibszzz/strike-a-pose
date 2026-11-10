"""Shared pygame shell: camera + pose -> game.update -> game.draw -> window.

Games draw onto a canvas in camera-pixel coordinates (so keypoints map 1:1); the
canvas is then scaled to the window with letterboxing.

Keys: D debug overlay, R reset, F fullscreen, Q / Esc quit.
"""

from __future__ import annotations

import time
from typing import Protocol

import cv2
import numpy as np
import pygame

from .audio import init_mixer
from .pose import SKELETON, PoseFrame
from .pose.tracker import PoseTracker

PLAYER_COLORS = [(80, 170, 255), (255, 120, 80)]


class Game(Protocol):
    title: str

    def update(self, frame: PoseFrame) -> None: ...
    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None: ...
    def reset(self) -> None: ...
    def render_camera(self, image_bgr: np.ndarray) -> np.ndarray:
        """Return an RGB image to use as the background."""
        ...
    def debug_lines(self) -> list[str]: ...


class FpsMeter:
    def __init__(self) -> None:
        self.last = time.perf_counter()
        self.fps = 0.0

    def tick(self) -> float:
        now = time.perf_counter()
        dt, self.last = now - self.last, now
        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1 / dt) if self.fps else 1 / dt
        return self.fps


def draw_skeletons(canvas: pygame.Surface, frame: PoseFrame, min_conf: float = 0.5) -> None:
    for idx, person in enumerate(frame.players):
        if person is None:
            continue
        color = PLAYER_COLORS[idx]
        # YOLO gives float32 numpy rows; pygame only accepts plain Python numbers as positions.
        pts = [(float(x), float(y)) for x, y in person.xy]
        for a, b in SKELETON:
            if person.conf[a] >= min_conf and person.conf[b] >= min_conf:
                pygame.draw.line(canvas, color, pts[a], pts[b], 4)
        for i, pt in enumerate(pts):
            if person.conf[i] >= min_conf:
                pygame.draw.circle(canvas, (255, 255, 255), pt, 5)


def run(make_game, camera_index: int = 0, imgsz: int = 640, device: str | None = None) -> None:
    pygame.init()
    init_mixer()
    tracker = PoseTracker(camera_index=camera_index, imgsz=imgsz, device=device)
    print(f"pose model running on: {tracker.device}")

    first = tracker.read()
    cam_h, cam_w = first.image.shape[:2]
    window_size = (cam_w, cam_h)
    screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
    canvas = pygame.Surface((cam_w, cam_h))
    game: Game = make_game((cam_w, cam_h))
    pygame.display.set_caption(game.title)
    debug_font = pygame.font.SysFont("menlo,monaco,courier", 20)

    debug, fullscreen = False, False
    fps = FpsMeter()
    frame = first
    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif event.key == pygame.K_d:
                        debug = not debug
                    elif event.key == pygame.K_r:
                        game.reset()
                    elif event.key == pygame.K_f:
                        fullscreen = not fullscreen
                        screen = (
                            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            if fullscreen
                            else pygame.display.set_mode(window_size, pygame.RESIZABLE)
                        )
                    elif hasattr(game, 'handle_key'):
                        game.handle_key(event.key)

            game.update(frame)

            rgb = game.render_camera(frame.image)
            canvas.blit(pygame.image.frombuffer(rgb.tobytes(), (cam_w, cam_h), "RGB"), (0, 0))
            game.draw(canvas, frame)
            if debug:
                draw_skeletons(canvas, frame)
                lines = [f"FPS {fps.fps:5.1f}  device {tracker.device}", *game.debug_lines()]
                for i, line in enumerate(lines):
                    canvas.blit(debug_font.render(line, True, (0, 255, 0), (0, 0, 0)), (10, cam_h - 30 * (len(lines) - i) - 10))

            sw, sh = screen.get_size()
            scale = min(sw / cam_w, sh / cam_h)
            size = (int(cam_w * scale), int(cam_h * scale))
            screen.fill((0, 0, 0))
            screen.blit(pygame.transform.scale(canvas, size), ((sw - size[0]) // 2, (sh - size[1]) // 2))
            pygame.display.flip()

            fps.tick()
            frame = tracker.read()
    finally:
        tracker.close()
        pygame.quit()


def sepia(image_bgr: np.ndarray) -> np.ndarray:
    """BGR in, sepia-toned RGB out."""
    m = np.array(
        [[0.189, 0.769, 0.393], [0.168, 0.686, 0.349], [0.131, 0.534, 0.272]], dtype=np.float32
    )
    return cv2.transform(image_bgr, m)
