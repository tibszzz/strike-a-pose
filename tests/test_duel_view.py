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
            start_delay=0.0,
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
    game = DuelGame(SIZE, config=DuelConfig(lives=1, start_delay=0.0, replay_speed=1.0, replay_freeze=0.2))
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


def _results_game(now: float = 10.0) -> DuelGame:
    game = DuelGame(
        SIZE,
        config=DuelConfig(
            debug=True,
            lives=1,
            round_result_time=0.5,
            match_result_min_time=0.5,
        ),
    )
    game._needs_ready_up = False
    game.now = now
    game.duel.debug_force_match_over(now, winner=0)
    game.win_msg = "test win"
    game.win_img = game._pick_cowboy()
    return game


def _art_box(game: DuelGame) -> pygame.Rect:
    """Mirror `_draw_results_body` art_box layout without drawing."""
    from main.end_screen.draw import CARD
    from main.ui.paper import Frame

    f = Frame(game.w, game.h)
    card = f.rect(*CARD)
    rect = pygame.Rect(
        card.x + f.px(44), card.y + f.px(62), card.width - f.px(88), card.height - f.px(92)
    )
    # headline + rows approximate: art sits on the right ~40% after lives column
    top = rect.y + f.px(64) + f.px(30)
    rows_rect = pygame.Rect(rect.x, top, min(int(rect.width * 0.6), f.px(660)), min(f.px(150), rect.bottom - top))
    return pygame.Rect(rows_rect.right + f.px(40), rect.y, rect.right - rows_rect.right - f.px(40), rect.height)


def test_results_art_box_shows_live_winner_crop():
    pygame.init()
    game = _results_game()
    canvas = pygame.Surface(SIZE)
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (10, 10, 10)
    # Bright BGR magenta in P1 box → RGB (255, 0, 255) after convert
    image[40:300, 40:180] = (255, 0, 255)
    p1 = _person((40, 40, 180, 300))
    frame = PoseFrame(image, game.now, (p1, None), [p1])
    game.draw(canvas, frame)
    art = _art_box(game)
    sample = canvas.get_at((art.centerx, art.centery))
    assert sample[0] > 200 and sample[2] > 200 and sample[1] < 80


def test_results_art_box_falls_back_when_winner_missing():
    pygame.init()
    game = _results_game()
    canvas = pygame.Surface(SIZE)
    image = np.full((SIZE[1], SIZE[0], 3), (255, 0, 255), np.uint8)  # solid magenta BGR
    frame = PoseFrame(image, game.now, (None, None), [])
    game.draw(canvas, frame)
    art = _art_box(game)
    sample = canvas.get_at((art.centerx, art.centery))
    # how-to PNG, not the solid camera magenta
    assert not (sample[0] > 200 and sample[2] > 200 and sample[1] < 40)


def test_debug_skip_to_results_after_gameplay():
    pygame.init()
    game = DuelGame(SIZE, config=DuelConfig(debug=True, lives=3))
    assert game.debug_skip_to_results() is False  # still in ready-up
    game._needs_ready_up = False
    game.now = 5.0
    game.duel.request_start(5.0)
    assert game.duel.phase != Phase.MATCH_OVER
    assert game.debug_skip_to_results() is True
    assert game.duel.phase == Phase.MATCH_OVER
    assert game.duel.match_winner is not None
    assert game.duel.can_restart(game.now)
    assert game.win_msg
