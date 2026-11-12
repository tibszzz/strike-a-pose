"""Shared pygame shell: camera + pose -> game.update -> game.draw -> window.

Games draw onto a canvas in camera-pixel coordinates (so keypoints map 1:1); the
canvas is then scaled to the window with letterboxing.

On bare launch (no CLI game), titles are preloaded after the first camera frame
so menu → StartGame reuses warm instances. Direct CLI launch skips preload.

Background rules:
- If the game defines `render_camera`, that image is always used (dodgeball).
- Else the canvas is filled with `background`; overlay mode (D) swaps in the live
  camera with skeletons on top (duel).

Keys: D overlay, R reset, F toggle fullscreen, Q quit app.
Starts fullscreen by default; pass fullscreen=False / --windowed for a window.
Esc leaves a playable game for the menu; on the splash or menu Esc quits.
Picking a game on the menu opens its how-to-play page (`make_how_to`) first;
that page emits StartGame(game_id) to enter the game's ready-up.
With `--debug`, arrow keys / Enter also feed MenuCommand (dev keyboard nav).
When the game sets wants_gestures, MediaPipe runs and attaches a snapshot.
`wants_gestures` is re-checked every frame; `gesture_hands` (default 2) sets
how many hands to track. Splash and menu read the snapshot themselves
(hold Thumb_Up / Closed_Fist / spatial select).
"""

from __future__ import annotations

import time
from typing import Callable, Mapping, Protocol

import cv2
import numpy as np
import pygame

from . import styles
from .audio import init_mixer
from .games.preload import GameCache, preload_games
from .games.registry import GameEntry
from .nav import (
    GestureCommandMapper,
    GestureRecognizerSession,
    MenuCommand,
    QuitApp,
    StartGame,
    load_gesture_nav_config,
)
from .pose import SKELETON, PoseFrame
from .pose.tracker import PoseTracker

PLAYER_COLORS = [(80, 170, 255), (255, 120, 80)]

KEY_TO_COMMAND = {
    pygame.K_UP: MenuCommand.MOVE_UP,
    pygame.K_DOWN: MenuCommand.MOVE_DOWN,
    pygame.K_LEFT: MenuCommand.MOVE_UP,
    pygame.K_RIGHT: MenuCommand.MOVE_DOWN,
    pygame.K_RETURN: MenuCommand.SELECT,
    pygame.K_KP_ENTER: MenuCommand.SELECT,
}


class Game(Protocol):
    title: str

    def update(self, frame: PoseFrame) -> None: ...
    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None: ...
    def reset(self) -> None: ...
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


def _blit_bgr(canvas: pygame.Surface, image_bgr: np.ndarray, size: tuple[int, int]) -> None:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    canvas.blit(pygame.image.frombuffer(rgb.tobytes(), size, "RGB"), (0, 0))


def _is_menu(game: Game) -> bool:
    return bool(getattr(game, "is_menu", False))


def _is_splash(game: Game) -> bool:
    return bool(getattr(game, "is_splash", False))


def _esc_quits(game: Game) -> bool:
    return _is_menu(game) or _is_splash(game)


def _owns_gestures(game: Game) -> bool:
    """Pages that read `gesture_snapshot` themselves (no rising-edge commands)."""
    return _is_menu(game) or _is_splash(game) or bool(getattr(game, "owns_gestures", False))


def _wants_gestures(game: Game) -> bool:
    return bool(getattr(game, "wants_gestures", False))


def _poll_nav(game: Game):
    if hasattr(game, "poll_nav"):
        return game.poll_nav()
    return None


def _sync_gestures(session: GestureRecognizerSession, mapper: GestureCommandMapper, game: Game) -> None:
    want = _wants_gestures(game)
    hands = int(getattr(game, "gesture_hands", 2))
    if want and (not session.active or session.num_hands != hands):
        session.stop()
        session.num_hands = hands
        session.start()
        mapper.reset()
    elif not want and session.active:
        session.stop()
        mapper.reset()


def _timestamp_ms(frame: PoseFrame) -> int:
    return int(frame.timestamp * 1000)


def run(
    *,
    registry: Mapping[str, GameEntry],
    make_menu: Callable[[tuple[int, int]], Game],
    make_splash: Callable[[tuple[int, int]], Game] | None = None,
    make_how_to: Callable[[tuple[int, int], str], Game | None] | None = None,
    initial_game: str | None = None,
    camera_index: int = 0,
    imgsz: int = 640,
    device: str | None = None,
    debug: bool = False,
    camera_width: int = 1920,
    camera_height: int = 1080,
    fullscreen: bool = True,
) -> None:
    pygame.init()
    init_mixer()
    tracker = PoseTracker(
        camera_index=camera_index,
        width=camera_width,
        height=camera_height,
        imgsz=imgsz,
        device=device,
    )
    print(f"pose model running on: {tracker.device}")

    gesture_config = load_gesture_nav_config()
    gestures = GestureRecognizerSession(gesture_config)
    mapper = GestureCommandMapper(
        min_score=gesture_config.min_score,
        refractory_ms=gesture_config.refractory_ms,
    )

    first = tracker.read()
    cam_h, cam_w = first.image.shape[:2]
    size = (cam_w, cam_h)
    window_size = size
    print(f"camera frame: {cam_w}x{cam_h} (requested {camera_width}x{camera_height})")
    screen = (
        pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        if fullscreen
        else pygame.display.set_mode(window_size, pygame.RESIZABLE)
    )
    canvas = pygame.Surface(size)

    # Bare launch: block on Loading… and warm every title before splash.
    # CLI direct launch skips preload (factory path only).
    cache = GameCache()
    if initial_game is None:
        warmed = preload_games(registry, size=size, frame=first, screen=screen)
        if warmed is None:
            gestures.close()
            tracker.close()
            pygame.quit()
            return
        cache = warmed

    def start_game(game_id: str | None) -> Game:
        if game_id is None:
            return make_menu(size)
        cached = cache.get(game_id)
        if cached is not None:
            cached.reset()
            return cached
        return registry[game_id].factory(size)

    if initial_game is None and make_splash is not None:
        game: Game = make_splash(size)
    else:
        game = start_game(initial_game)
    pygame.display.set_caption(game.title)
    _sync_gestures(gestures, mapper, game)
    debug_font = styles.load_font(styles.FONT, 20)

    overlay = False
    fps = FpsMeter()
    frame = first
    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        running = False
                    elif event.key == pygame.K_ESCAPE:
                        if _esc_quits(game):
                            running = False
                        else:
                            game = start_game(None)
                            pygame.display.set_caption(game.title)
                            _sync_gestures(gestures, mapper, game)
                    elif event.key == pygame.K_d:
                        overlay = not overlay
                    elif event.key == pygame.K_r:
                        game.reset()
                    elif event.key == pygame.K_f:
                        fullscreen = not fullscreen
                        screen = (
                            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            if fullscreen
                            else pygame.display.set_mode(window_size, pygame.RESIZABLE)
                        )
                    else:
                        command = KEY_TO_COMMAND.get(event.key) if debug else None
                        if command is not None and hasattr(game, "handle_command"):
                            game.handle_command(command)
                        elif hasattr(game, "handle_key"):
                            game.handle_key(event.key)

            _sync_gestures(gestures, mapper, game)  # games may toggle wants_gestures per screen
            if gestures.active:
                snap = gestures.recognize(
                    frame.image, _timestamp_ms(frame), people=frame.people
                )
                if _wants_gestures(game):
                    game.gesture_snapshot = snap
                # Splash/menu own gesture actions from the snapshot; other
                # gesture games still use the rising-edge label mapper.
                if not _owns_gestures(game) and hasattr(game, "handle_command"):
                    command = mapper.feed(snap, _timestamp_ms(frame))
                    if command is not None:
                        game.handle_command(command)

            game.update(frame)
            nav = _poll_nav(game)
            if isinstance(nav, QuitApp):
                running = False
            elif isinstance(nav, StartGame):
                # Menu picks go through the game's how-to-play page first.
                how_to = (
                    make_how_to(size, nav.game_id)
                    if make_how_to is not None and nav.game_id is not None and _is_menu(game)
                    else None
                )
                game = how_to if how_to is not None else start_game(nav.game_id)
                pygame.display.set_caption(game.title)
                _sync_gestures(gestures, mapper, game)
                game.update(frame)

            if hasattr(game, "render_camera"):
                _blit_bgr(canvas, game.render_camera(frame.image), size)
            elif overlay:
                _blit_bgr(canvas, frame.image, size)
            else:
                canvas.fill(game.background)
            game.draw(canvas, frame)
            if overlay:
                draw_skeletons(canvas, frame)
                lines = [f"FPS {fps.fps:5.1f}  device {tracker.device}", *game.debug_lines()]
                for i, line in enumerate(lines):
                    canvas.blit(
                        debug_font.render(line, True, (0, 255, 0), (0, 0, 0)),
                        (10, cam_h - 30 * (len(lines) - i) - 10),
                    )

            sw, sh = screen.get_size()
            scale = min(sw / cam_w, sh / cam_h)
            scaled = (int(cam_w * scale), int(cam_h * scale))
            screen.fill((0, 0, 0))
            screen.blit(
                pygame.transform.scale(canvas, scaled),
                ((sw - scaled[0]) // 2, (sh - scaled[1]) // 2),
            )
            pygame.display.flip()

            fps.tick()
            frame = tracker.read()
    finally:
        gestures.close()
        tracker.close()
        pygame.quit()
