"""Smoke test: every screen of the duel view renders headless without errors."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.games.duel.game import DuelGame
from main.games.duel.logic import DuelConfig, Phase
from main.pose import Person, PoseFrame, PoseState

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
    game = DuelGame(SIZE, config=DuelConfig(lives=1))
    game.duel.rng = FixedRng(1.6)
    canvas = pygame.Surface(SIZE)
    p1 = _person((40, 40, 180, 300))
    p2 = _person((400, 40, 560, 300))
    frame = _frame((p1, p2))

    t, seen = 0.0, set()
    floated = False
    # idle -> READY -> P1 draws early in STEADY -> P2 draws after BANG -> winner screen
    for states in [(H, H)] * 40 + [(D, H)] * 120 + [(D, D)] * 20 + [(H, H)] * 170:
        t += DT
        game.step(t, states)
        game.draw(canvas, frame)
        seen.add(game.duel.phase)
        floated |= bool(game.floaters)

    assert {Phase.WAIT_START, Phase.READY, Phase.STEADY, Phase.BANG, Phase.MATCH_OVER} <= seen
    assert floated
    assert game.duel.phase == Phase.MATCH_OVER and game.duel.match_winner == 1
    assert game.shot_msg and game.win_msg and game.win_img is not None
    assert game.duel.can_restart(t)


def test_preview_placeholder_when_missing():
    pygame.init()
    game = DuelGame(SIZE, config=DuelConfig(lives=1))
    canvas = pygame.Surface(SIZE)
    game.step(0.0, (H, H))
    game.draw(canvas, _frame((None, None)))
    # inset from border/label: placeholder fill is theme.hint, not the camera RGB
    rect = game._preview_rect(0)
    sample = canvas.get_at((rect.left + 8, rect.top + 8))
    assert sample[:3] == (140, 140, 140)
