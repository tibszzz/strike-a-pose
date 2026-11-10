"""Smoke test: every screen of the duel view renders headless without errors."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.games.duel.game import DuelGame
from main.games.duel.logic import DuelConfig, Phase
from main.pose import PoseFrame, PoseState

from test_duel_logic import FixedRng

H, D = PoseState.NEUTRAL, PoseState.DRAWN
SIZE = (640, 360)
DT = 1 / 30


def test_all_screens_render():
    pygame.init()
    game = DuelGame(SIZE, config=DuelConfig(lives=1))
    game.duel.rng = FixedRng(1.6)
    canvas = pygame.Surface(SIZE)
    frame = PoseFrame(np.zeros((SIZE[1], SIZE[0], 3), np.uint8), 0.0, (None, None), [])

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
