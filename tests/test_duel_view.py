"""Smoke test: every screen of the duel view renders headless without errors."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.games.duel.game import DuelGame
from main.games.duel.logic import DuelConfig, Phase
from main.pose import Person, PoseFrame, PoseState
from main.ui import paper

from test_duel_logic import FixedRng

H, D = PoseState.NEUTRAL, PoseState.DRAWN
SIZE = (640, 360)
DT = 1 / 30


def _frame(players):
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (40, 80, 120)
    return PoseFrame(image, 0.0, players, [p for p in players if p is not None])


def _person(box):
    return Person(xy=np.zeros((17, 2)), conf=np.ones(17), box=box)


def test_all_screens_render():
    pygame.init()
    game = DuelGame(
        SIZE,
        config=DuelConfig(
            lives=1,
            replay_speed=1.0,
            replay_freeze=0.0,
            round_result_time=0.5,
            match_result_min_time=0.5,
        ),
    )
    game.duel.rng = FixedRng(1.6)
    canvas = pygame.Surface(SIZE)
    p1 = _person((40, 40, 180, 300))
    p2 = _person((400, 40, 560, 300))
    frame = _frame((p1, p2))

    t, seen = 0.0, set()
    floated = False
    game.draw(canvas, frame)
    seen.add(game.duel.phase)
    # ready-up request_start -> READY -> P1 draws early in STEADY -> P2 draws after BANG -> replay -> winner
    game.duel.request_start(0.0)
    game._needs_ready_up = False
    game._roster_seed_x = [110.0, 480.0]
    for states in [(H, H)] * 40 + [(D, H)] * 120 + [(D, D)] * 20 + [(H, H)] * 220:
        t += DT
        frame.image[:] = (40, 80, int(120 + (t * 30) % 80))
        game.step(t, states)
        # Mirror update()'s record tick without re-classifying poses.
        if game.duel.phase == Phase.BANG and game.recorder.active:
            game.recorder.push(frame.image, t)
        game.draw(canvas, frame)
        seen.add(game.duel.phase)
        floated |= bool(game.floaters)

    assert {
        Phase.WAIT_START,
        Phase.READY,
        Phase.STEADY,
        Phase.BANG,
        Phase.REPLAY,
        Phase.MATCH_OVER,
    } <= seen
    assert floated
    assert game.duel.phase == Phase.MATCH_OVER and game.duel.match_winner == 1
    assert game.shot_msg and game.win_msg and game.win_img is not None
    assert game.duel.can_restart(t)


def test_preview_placeholder_when_missing():
    pygame.init()
    game = DuelGame(SIZE, config=DuelConfig(lives=1))
    canvas = pygame.Surface(SIZE)
    game.duel.request_start(0.0)
    game._needs_ready_up = False
    game.now = 0.0
    game.draw(canvas, _frame((None, None)))
    # inset from border/label: placeholder fill is faint paper ink, not the camera RGB
    rect = game._preview_rect(0)
    sample = canvas.get_at((rect.left + 12, rect.top + 12))
    assert sample[:3] == paper.INK_FAINT


def test_replay_screen_cover_blits():
    pygame.init()
    game = DuelGame(SIZE, config=DuelConfig(lives=1, replay_speed=1.0, replay_freeze=0.2))
    game.duel.rng = FixedRng(0.1)
    canvas = pygame.Surface(SIZE)
    p1 = _person((40, 40, 180, 300))
    p2 = _person((400, 40, 560, 300))

    t = 0.0
    game.duel.request_start(t)
    game._needs_ready_up = False
    game._roster_seed_x = [110.0, 480.0]
    for states in [(H, H)] * 40 + [(H, H)] * 60 + [(D, H)] * 30:
        t += DT
        image = np.full((SIZE[1], SIZE[0], 3), (30, 90, 180), np.uint8)
        game.step(t, states)
        if game.duel.phase == Phase.BANG and game.recorder.active:
            game.recorder.push(image, t)
        game.draw(canvas, PoseFrame(image, t, (p1, p2), [p1, p2]))
        if game.duel.phase == Phase.REPLAY:
            break
    else:
        raise AssertionError("never reached REPLAY")

    # BGR (30,90,180) stores as RGB (180,90,30); center should not be the white page.
    center = canvas.get_at((SIZE[0] // 2, SIZE[1] // 2))
    assert center[0] > 100 and center[:3] != (245, 245, 240)
