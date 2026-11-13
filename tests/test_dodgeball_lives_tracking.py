"""Dodgeball lives-by-count table, sticky seats, and out-label colors."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pygame")

from main.games.dodgeball import dodgeball as d
from main.pose import Person
from main.ui.paper import INK_FAINT
from main.ui import paper


def _person(cx: float, half: float = 40.0) -> Person:
    xy = np.zeros((17, 2), dtype=np.float32)
    xy[:, 0] = cx
    xy[0] = (cx, 80.0)  # nose
    conf = np.ones(17, dtype=np.float32)
    return Person(xy=xy, conf=conf, box=(cx - half, 40.0, cx + half, 360.0))


@pytest.mark.parametrize(
    "count,lives",
    [(1, 3), (2, 3), (3, 2), (4, 1)],
)
def test_lives_for_player_count_table(count, lives):
    assert d.lives_for_player_count(count) == lives


def test_start_applies_lives_table():
    game = d.DodgeballGame((640, 480))
    game.start(3, seed_x=[100.0, 320.0, 520.0])
    assert game.max_lives == 2
    assert game.lives == [2, 2, 2]


def test_seat_label_color_grays_out():
    assert d.seat_label_color(1, 2) == paper.player_ink(1)
    assert d.seat_label_color(2, 0) == INK_FAINT


def test_sticky_assign_keeps_seats_when_players_cross():
    game = d.DodgeballGame((640, 480))
    game.start(2, seed_x=[160.0, 480.0])
    left, right = _person(160.0), _person(480.0)
    slots = game._assign_players([left, right])
    assert slots[0] is left and slots[1] is right

    # Same bodies, swapped sides: seats must follow last_x, not left-to-right.
    crossed = game._assign_players([_person(480.0), _person(160.0)])
    assert crossed[0].center_x == pytest.approx(160.0)
    assert crossed[1].center_x == pytest.approx(480.0)


def test_sticky_assign_ignores_extra_detection():
    game = d.DodgeballGame((640, 480))
    game.start(2, seed_x=[160.0, 480.0])
    p1, p2, spectator = _person(160.0), _person(480.0), _person(320.0)
    slots = game._assign_players([p1, spectator, p2])
    assert slots[0].center_x == pytest.approx(160.0)
    assert slots[1].center_x == pytest.approx(480.0)


def test_out_player_still_gets_a_slot_when_visible():
    game = d.DodgeballGame((640, 480))
    game.start(2, seed_x=[160.0, 480.0])
    game.lives = [3, 0]
    slots = game._assign_players([_person(160.0), _person(480.0)])
    assert slots[1] is not None
    assert d.seat_label_color(2, game.lives[1]) == INK_FAINT


def test_min_players_default_is_two():
    assert d.DodgeballGame((640, 480)).config.min_players == 2
