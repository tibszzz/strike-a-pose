"""Strike final RESULTS: live winner PiP + P# above the feed."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.end_screen.draw import CARD
from main.games.strike.play import StrikeGame
from main.games.strike.screens import FinalScreen, Standing
from main.pose import Person, PoseFrame
from main.settings import StrikeConfig
from main.ui import paper
from main.ui.paper import Frame


SIZE = (640, 360)


def _person(box) -> Person:
    return Person(xy=np.zeros((17, 2)), conf=np.ones(17), box=box)


def _final_game(*, winner: int = 1, seeds: list[float] | None = None) -> StrikeGame:
    game = StrikeGame(SIZE, config=StrikeConfig(debug=True, rounds=1))
    game._in_ready_up = False
    game._screen = FinalScreen(
        standings=(
            Standing(place=1, player=winner, total=10),
            Standing(place=2, player=2 if winner == 1 else 1, total=3),
        ),
        round_scores=((10,), (3,)),
        total_rounds=1,
    )
    game._end.reset()
    game._frame_ts = 10.0
    if seeds is None:
        seeds = [110.0, 480.0]
    game._logic._roster_seed_x = list(seeds)
    game._logic._player_count = 2
    from main.games.strike.logic import _Phase

    game._logic._phase = _Phase.FINAL
    return game


def _art_box(game: StrikeGame) -> pygame.Rect:
    """Mirror `_draw_final_body` art column (~25% right) without drawing."""
    f = Frame(game.w, game.h)
    card = f.rect(*CARD)
    rect = pygame.Rect(
        card.x + f.px(44), card.y + f.px(62), card.width - f.px(88), card.height - f.px(92)
    )
    # headline ~58 design px; table starts below — art column uses full rect height
    gap = f.px(40)
    art_w = max(1, int(rect.width * 0.25) - gap)
    table_w = max(1, rect.width - art_w - gap)
    return pygame.Rect(rect.x + table_w + gap, rect.y, art_w, rect.height)


def test_final_wants_people():
    game = _final_game()
    assert game._logic.wants_people(0.0) is True


def test_final_art_shows_live_winner_crop():
    pygame.init()
    game = _final_game(winner=1)
    canvas = pygame.Surface(SIZE)
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (10, 10, 10)
    # Bright BGR magenta in P1 box → RGB magenta after convert
    image[40:300, 40:180] = (255, 0, 255)
    p1 = _person((40, 40, 180, 300))
    p2 = _person((400, 40, 560, 300))
    frame = PoseFrame(image, game._frame_ts, (p1, p2), [p1, p2])
    game.draw(canvas, frame)
    art = _art_box(game)
    # Sample feed center (below the P# tag band)
    sample = canvas.get_at((art.centerx, art.centery + 20))
    assert sample[0] > 200 and sample[2] > 200 and sample[1] < 80


def test_final_art_shows_feed_when_winner_missing():
    pygame.init()
    game = _final_game(winner=1)
    canvas = pygame.Surface(SIZE)
    image = np.full((SIZE[1], SIZE[0], 3), (255, 0, 255), np.uint8)
    frame = PoseFrame(image, game._frame_ts, (None, None), [])
    game.draw(canvas, frame)
    art = _art_box(game)
    sample = canvas.get_at((art.centerx, art.centery + 20))
    assert sample[0] > 200 and sample[2] > 200 and sample[1] < 40


def test_final_art_draws_p_label_above_feed():
    pygame.init()
    game = _final_game(winner=1)
    canvas = pygame.Surface(SIZE)
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (10, 10, 10)
    p1 = _person((40, 40, 180, 300))
    frame = PoseFrame(image, game._frame_ts, (p1, None), [p1])
    game.draw(canvas, frame)
    art = _art_box(game)
    ink = paper.player_ink(1)
    tag_band = art.top + 40
    found = False
    for y in range(art.top, min(tag_band, art.bottom)):
        for x in range(art.left + 4, art.right - 4, 3):
            sample = canvas.get_at((x, y))[:3]
            if all(abs(sample[i] - ink[i]) < 40 for i in range(3)):
                found = True
                break
        if found:
            break
    assert found


def test_results_preview_resets_on_leave_final():
    game = _final_game()
    game._results_preview.update(_person((40, 40, 180, 300)), now=1.0, frame_w=640, frame_h=360)
    assert game._results_preview._box is not None
    game.reset()
    assert game._results_preview._box is None
