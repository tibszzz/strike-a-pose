"""Warm playable titles at boot so open reuses constructed instances.

Owns the instance cache. Registry stays factory-only for fallback and CLI.
"""

from __future__ import annotations

from typing import Any, Mapping

import cv2
import numpy as np
import pygame

from main import styles
from main.games.registry import GameEntry
from main.pose import PoseFrame

Size = tuple[int, int]


class GameCache:
    """Prebuilt title instances keyed by registry id."""

    def __init__(self) -> None:
        self._games: dict[str, Any] = {}

    def get(self, game_id: str) -> Any | None:
        return self._games.get(game_id)

    def put(self, game_id: str, game: Any) -> None:
        self._games[game_id] = game


def _blit_bgr(canvas: pygame.Surface, image_bgr: np.ndarray, size: Size) -> None:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    canvas.blit(pygame.image.frombuffer(rgb.tobytes(), size, "RGB"), (0, 0))


def _warm_paint(game: Any, canvas: pygame.Surface, frame: PoseFrame, size: Size) -> None:
    if hasattr(game, "render_camera"):
        _blit_bgr(canvas, game.render_camera(frame.image), size)
    else:
        canvas.fill(getattr(game, "background", (0, 0, 0)))
    game.draw(canvas, frame)


def _show_loading(screen: pygame.Surface, font: pygame.font.Font) -> None:
    screen.fill((0, 0, 0))
    text = font.render("Loading...", True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=screen.get_rect().center))
    pygame.display.flip()


def _pump() -> bool:
    """Pump events so the window stays alive. False if the user asked to quit."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
            return False
    return True


def preload_games(
    registry: Mapping[str, GameEntry],
    *,
    size: Size,
    frame: PoseFrame,
    screen: pygame.Surface,
) -> GameCache | None:
    """Construct + one update/draw per title. Off-screen only; Loading… on screen.

    Returns None if the user quits during warm-up. Partial failures are logged;
    successful instances stay in the cache.
    """
    cache = GameCache()
    font = styles.load_font(styles.FONT, 36)
    warm_canvas = pygame.Surface(size)
    _show_loading(screen, font)

    for game_id, entry in registry.items():
        if not _pump():
            return None
        try:
            game = entry.factory(size)
            game.update(frame)
            _warm_paint(game, warm_canvas, frame, size)
            cache.put(game_id, game)
        except Exception as exc:
            print(f"preload {game_id} failed: {exc}")
        _show_loading(screen, font)

    if not _pump():
        return None
    return cache
