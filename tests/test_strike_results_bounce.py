"""Round-winner score bounce on Strike ResultsScreen."""

from __future__ import annotations

import math

import pytest
from builders import mirrored, person_striking

from main.games.strike.game import (
    RESULTS_WINNER_BOUNCE_HZ,
    RESULTS_WINNER_BOUNCE_PX,
    round_high_scorers,
    winner_score_bounce_y,
)
from main.games.strike.screens import PlayerResult, ResultsScreen
from test_game import (
    COUNTDOWN,
    SPOTS,
    _results_idle_at,
    new_game,
    play_round,
    start_game,
)


def _player(seat: int, round_score: int) -> PlayerResult:
    return PlayerResult(
        player=seat,
        joints={},
        box=(0.0, 0.0, 10.0, 10.0),
        round_score=round_score,
        total=round_score,
    )


def test_round_high_scorers_sole_winner():
    assert round_high_scorers((_player(1, 40), _player(2, 90), _player(3, 70))) == {2}


def test_round_high_scorers_ties_all_high():
    assert round_high_scorers((_player(1, 80), _player(2, 80), _player(3, 50))) == {
        1,
        2,
    }


def test_round_high_scorers_empty():
    assert round_high_scorers(()) == frozenset()


def test_winner_score_bounce_y_rest_at_lock_then_rises():
    assert winner_score_bounce_y(0.0) == 0
    # At 1 Hz, t=0.25s is peak upward (negative canvas Y).
    assert winner_score_bounce_y(0.25 / RESULTS_WINNER_BOUNCE_HZ) == -RESULTS_WINNER_BOUNCE_PX
    assert winner_score_bounce_y(0.5 / RESULTS_WINNER_BOUNCE_HZ) == 0
    assert winner_score_bounce_y(0.75 / RESULTS_WINNER_BOUNCE_HZ) == RESULTS_WINNER_BOUNCE_PX


def test_winner_score_bounce_y_matches_sine_formula():
    elapsed = 0.37
    expected = round(
        -RESULTS_WINNER_BOUNCE_PX
        * math.sin(elapsed * math.tau * RESULTS_WINNER_BOUNCE_HZ)
    )
    assert winner_score_bounce_y(elapsed) == expected


def test_bounce_elapsed_none_until_lock_then_tracks_time():
    game, _ = new_game(
        results_hold_s=0.0,
        results_reveal_s=0.5,
        results_reveal_hz=10.0,
        results_advance_s=5.0,
    )
    start_game(game)
    revealing = play_round(game, 0.0, lambda target: [
        person_striking(target.joints, center_x=SPOTS[0]),
        person_striking(mirrored(target.joints), center_x=SPOTS[1]),
    ])
    assert isinstance(revealing, ResultsScreen)
    assert not revealing.idle
    assert revealing.bounce_elapsed_s is None

    idle_at = _results_idle_at(game, COUNTDOWN)
    locked = game.step(idle_at)
    assert isinstance(locked, ResultsScreen)
    assert locked.idle
    assert locked.bounce_elapsed_s == pytest.approx(0.0)

    mid = game.step(idle_at + 0.4)
    assert isinstance(mid, ResultsScreen)
    assert mid.bounce_elapsed_s == pytest.approx(0.4)


def test_locked_unequal_scores_mark_sole_high_scorer():
    game, _ = new_game(
        results_hold_s=0.0,
        results_reveal_s=0.0,
        results_advance_s=5.0,
    )
    start_game(game)

    def strike(target):
        return [
            person_striking(target.joints, center_x=SPOTS[0]),
            person_striking(mirrored(target.joints), center_x=SPOTS[1]),
        ]

    play_round(game, 0.0, strike)
    locked = game.step(_results_idle_at(game, COUNTDOWN))
    assert isinstance(locked, ResultsScreen)
    assert locked.idle
    winners = round_high_scorers(locked.players)
    assert winners == {1}
    assert locked.players[0].round_score > locked.players[1].round_score


def test_locked_perfect_tie_marks_all_high_scorers():
    game, _ = new_game(
        results_hold_s=0.0,
        results_reveal_s=0.0,
        results_advance_s=5.0,
    )
    start_game(game)
    play_round(
        game,
        0.0,
        lambda target: [
            person_striking(target.joints, center_x=SPOTS[0]),
            person_striking(target.joints, center_x=SPOTS[1]),
        ],
    )
    locked = game.step(_results_idle_at(game, COUNTDOWN))
    assert isinstance(locked, ResultsScreen)
    assert round_high_scorers(locked.players) == {1, 2}
