"""Dodgeball final RESULTS: live winner PiP + P# above the feed."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.end_screen.draw import CARD
from main.games.dodgeball.dodgeball import DodgeballGame
from main.pose import Person, PoseFrame
from main.settings import DodgeballConfig
from main.ui import paper
from main.ui.paper import Frame

SIZE = (640, 360)


def _person(box) -> Person:
    return Person(xy=np.zeros((17, 2)), conf=np.ones(17), box=box)


def _results_game(*, lives: list[int] | None = None) -> DodgeballGame:
    game = DodgeballGame(SIZE, config=DodgeballConfig(debug=True))
    game.in_lobby = False
    game.player_count = 2
    game.max_lives = 3
    game.lives = list(lives) if lives is not None else [3, 0]
    game.last_x = [110.0, 480.0]
    game.game_over = True
    game.paused = True
    game._end.reset()
    game._frame_ts = 10.0
    return game


def _art_box(game: DodgeballGame) -> pygame.Rect:
    """Mirror `_draw_results_body` art_box layout without drawing."""
    f = Frame(game.w, game.h)
    card = f.rect(*CARD)
    rect = pygame.Rect(
        card.x + f.px(44), card.y + f.px(62), card.width - f.px(88), card.height - f.px(92)
    )
    top = rect.y + f.px(64) + f.px(28)
    rows_rect = pygame.Rect(
        rect.x, top, min(int(rect.width * 0.6), f.px(660)), rect.bottom - top
    )
    return pygame.Rect(
        rows_rect.right + f.px(40),
        rect.y,
        rect.right - rows_rect.right - f.px(40),
        rect.height,
    )


def test_results_art_box_shows_live_winner_crop():
    pygame.init()
    game = _results_game()
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
    sample = canvas.get_at((art.centerx, art.centery + 20))
    assert sample[0] > 200 and sample[2] > 200 and sample[1] < 80


def test_results_art_box_shows_feed_when_winner_missing():
    pygame.init()
    game = _results_game()
    canvas = pygame.Surface(SIZE)
    image = np.full((SIZE[1], SIZE[0], 3), (255, 0, 255), np.uint8)
    frame = PoseFrame(image, game._frame_ts, (None, None), [])
    game.draw(canvas, frame)
    art = _art_box(game)
    sample = canvas.get_at((art.centerx, art.centery + 20))
    assert sample[0] > 200 and sample[2] > 200 and sample[1] < 40


def test_results_art_box_draws_winner_label():
    pygame.init()
    game = _results_game()
    canvas = pygame.Surface(SIZE)
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (10, 10, 10)
    p1 = _person((40, 40, 180, 300))
    frame = PoseFrame(image, game._frame_ts, (p1, None), [p1])
    game.draw(canvas, frame)
    art = _art_box(game)
    ink = paper.player_ink(1)
    tag_band = art.top + game._winner_tag_face.get_height() + 8
    found = False
    for y in range(art.top, min(tag_band, art.bottom)):
        for x in range(art.left + 8, art.right - 8, 4):
            sample = canvas.get_at((x, y))[:3]
            if all(abs(sample[i] - ink[i]) < 40 for i in range(3)):
                found = True
                break
        if found:
            break
    assert found


def test_nobody_wins_has_no_winner_tag():
    pygame.init()
    game = _results_game(lives=[0, 0])
    canvas = pygame.Surface(SIZE)
    image = np.zeros((SIZE[1], SIZE[0], 3), np.uint8)
    image[:] = (10, 10, 10)
    p1 = _person((40, 40, 180, 300))
    frame = PoseFrame(image, game._frame_ts, (p1, None), [p1])
    game.draw(canvas, frame)
    art = _art_box(game)
    ink = paper.player_ink(1)
    tag_band = art.top + game._winner_tag_face.get_height() + 8
    for y in range(art.top, min(tag_band, art.bottom)):
        for x in range(art.left + 8, art.right - 8, 4):
            sample = canvas.get_at((x, y))[:3]
            assert not all(abs(sample[i] - ink[i]) < 40 for i in range(3))
