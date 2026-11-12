"""Shared Replay / Menu end-screen chooser."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.end_screen import EndChoice, EndScreen, draw_end_screen
from main.nav import GestureSnapshot, MenuCommand, StartGame
from main.pose import PoseFrame
from main.styles import SHELL


def _landmarks_at(x: float, y: float, count: int = 21) -> tuple[tuple[float, float], ...]:
    pts = [(0.0, 0.0)] * count
    pts[0] = (x, y)
    pts[8] = (x, y)  # INDEX_FINGERTIP
    return tuple(pts)


def test_tip_hard_locks_tile():
    pygame.init()
    end = EndScreen((640, 480), config=None)
    tip = end.tile_rects()[0].center
    snap = GestureSnapshot(label=None, score=0.0, landmarks=_landmarks_at(*tip))
    assert end.update(snap, 1.0) is None
    assert end.hard_lock == 0


def test_fist_hold_confirms_replay():
    pygame.init()
    end = EndScreen((640, 480))
    tip = end.tile_rects()[0].center  # REPLAY
    end.update(GestureSnapshot(label=None, score=0.0, landmarks=_landmarks_at(*tip)), 1.0)
    fist = GestureSnapshot(label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip))
    assert end.update(fist, 1.0) is None
    assert end.update(fist, 1.4) is None
    assert end.update(fist, 1.5) is EndChoice.REPLAY


def test_fist_hold_confirms_menu():
    pygame.init()
    end = EndScreen((640, 480))
    tip = end.tile_rects()[1].center  # MENU
    end.update(GestureSnapshot(label=None, score=0.0, landmarks=_landmarks_at(*tip)), 1.0)
    fist = GestureSnapshot(label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip))
    end.update(fist, 1.0)
    assert end.update(fist, 2.0) is EndChoice.MENU


def test_keyboard_select_confirms():
    pygame.init()
    end = EndScreen((640, 480))
    assert end.handle_command(MenuCommand.MOVE_DOWN) is None
    assert end.hard_lock == 0
    assert end.handle_command(MenuCommand.MOVE_DOWN) is None
    assert end.hard_lock == 1
    assert end.handle_command(MenuCommand.SELECT) is EndChoice.MENU


def test_draw_end_screen_smoke():
    pygame.init()
    end = EndScreen((640, 480))
    canvas = pygame.Surface((640, 480))
    draw_end_screen(canvas, end, theme=SHELL, timestamp=0.5)


def test_duel_end_screen_replay_and_menu():
    pygame.init()
    from main.games.duel.game import DuelGame
    from main.games.duel.logic import DuelConfig, Phase

    game = DuelGame(
        (640, 360),
        config=DuelConfig(
            lives=1,
            round_result_time=0.1,
            match_result_min_time=0.1,
            replay_speed=1.0,
            replay_freeze=0.0,
        ),
    )
    assert game._needs_ready_up is True
    game.duel.request_start(0.0)
    game._needs_ready_up = False
    game._roster_seed_x = [100.0, 500.0]
    # Force match over
    game.duel.scores = [0, 1]
    game.duel.match_winner = 1
    game.duel._enter(Phase.MATCH_OVER, 0.0)
    game.duel._match_over_pending = False
    game.now = 1.0
    assert game._in_end_screen()
    assert game.wants_gestures is True

    tip = game._end.tile_rects()[0].center
    game.gesture_snapshot = GestureSnapshot(
        label=None, score=0.0, landmarks=_landmarks_at(*tip)
    )
    frame = PoseFrame(np.zeros((360, 640, 3), np.uint8), 1.0, (None, None), [])
    game.update(frame)
    game.gesture_snapshot = GestureSnapshot(
        label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip)
    )
    game.update(PoseFrame(frame.image, 1.0, (None, None), []))
    game.update(PoseFrame(frame.image, 2.0, (None, None), []))
    assert game._needs_ready_up is True
    assert game.poll_nav() is None

    # Re-enter end screen and choose menu
    game._needs_ready_up = False
    game.duel._enter(Phase.MATCH_OVER, 0.0)
    game.now = 1.0
    game._end.reset()
    tip_menu = game._end.tile_rects()[1].center
    game.gesture_snapshot = GestureSnapshot(
        label=None, score=0.0, landmarks=_landmarks_at(*tip_menu)
    )
    game.update(PoseFrame(frame.image, 3.0, (None, None), []))
    game.gesture_snapshot = GestureSnapshot(
        label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip_menu)
    )
    game.update(PoseFrame(frame.image, 3.0, (None, None), []))
    game.update(PoseFrame(frame.image, 4.0, (None, None), []))
    assert game.poll_nav() == StartGame(None)


def test_strike_final_end_screen():
    pygame.init()
    from main.games.strike.play import StrikeGame
    from main.games.strike.screens import FinalScreen, Standing

    game = StrikeGame((640, 480))
    game._in_ready_up = False
    game._screen = FinalScreen(standings=(Standing(place=1, player=1, total=10),))
    game._end.reset()
    assert game.wants_gestures is True
    assert game._in_end_screen()

    tip = game._end.tile_rects()[0].center
    frame = PoseFrame(np.zeros((480, 640, 3), np.uint8), 1.0, (None, None), [])
    game.gesture_snapshot = GestureSnapshot(
        label=None, score=0.0, landmarks=_landmarks_at(*tip)
    )
    game.update(frame)
    game.gesture_snapshot = GestureSnapshot(
        label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip)
    )
    game.update(PoseFrame(frame.image, 1.0, (None, None), []))
    game.update(PoseFrame(frame.image, 2.0, (None, None), []))
    assert game._in_ready_up is True


def test_dodgeball_game_over_replay():
    pygame.init()
    from main.games.dodgeball.dodgeball import DodgeballGame

    game = DodgeballGame((640, 480))
    game.start(1, seed_x=[320.0])
    game.lives = [0]
    game.game_over = True
    game.paused = True
    game._end.reset()
    assert game.wants_gestures is True

    tip = game._end.tile_rects()[0].center
    frame = PoseFrame(np.zeros((480, 640, 3), np.uint8), 1.0, (None, None), [])
    game.gesture_snapshot = GestureSnapshot(
        label=None, score=0.0, landmarks=_landmarks_at(*tip)
    )
    game.update(frame)
    game.gesture_snapshot = GestureSnapshot(
        label="Closed_Fist", score=1.0, landmarks=_landmarks_at(*tip)
    )
    game.update(PoseFrame(frame.image, 1.0, (None, None), []))
    game.update(PoseFrame(frame.image, 2.0, (None, None), []))
    assert game.in_lobby is True
    assert game.game_over is False
