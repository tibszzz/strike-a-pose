"""Dodgeball's pre-launch countdown: 3 seconds, Strike's big digit."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pygame")

from main.games.dodgeball import dodgeball as d
from main.pose import PoseFrame


def _frame() -> PoseFrame:
    return PoseFrame(np.zeros((480, 640, 3), np.uint8), 0.0, (None, None), [])


def _record_sounds(monkeypatch, game) -> list[str]:
    played: list[str] = []
    names = {id(s): n for n, s in game.sounds.items()}
    monkeypatch.setattr(d.audio, "play", lambda s: played.append(names.get(id(s), "?")))
    return played


def _run_countdown(game) -> int:
    frames = 0
    while game.countdown > 0:
        game.update(_frame())
        frames += 1
    return frames


def test_match_start_countdown_is_three_seconds(monkeypatch):
    game = d.DodgeballGame((640, 480))
    played = _record_sounds(monkeypatch, game)
    game.start(1)
    assert game.countdown == 3 * d.FPS
    assert _run_countdown(game) == 3 * d.FPS
    assert played == ["match_start", "tick", "tick", "go"]  # jingle stands in for "3"


def test_hit_restarts_by_itself_after_five_seconds(monkeypatch):
    game = d.DodgeballGame((640, 480))
    game.start(1)
    _run_countdown(game)
    played = _record_sounds(monkeypatch, game)

    game._lose_life(0, "HIT!")

    assert not game.paused  # no waiting for R or a gesture
    assert game.countdown == 5 * d.FPS
    assert game.hit_message == "P1 HIT!"
    assert _run_countdown(game) == 5 * d.FPS
    assert played == ["tick", "tick", "tick", "go"]  # only the visible 3, 2, 1
    assert game.lives == [d.lives_for_player_count(1) - 1]


def test_r_does_nothing_mid_match():
    game = d.DodgeballGame((640, 480))
    game.start(1)
    _run_countdown(game)
    game._lose_life(0, "HIT!")
    before = game.countdown
    game.reset()
    assert game.countdown == before and not game.in_lobby


def test_last_life_still_ends_the_match_and_waits_there():
    game = d.DodgeballGame((640, 480))
    game.start(1)
    _run_countdown(game)
    game.lives = [1]
    game._lose_life(0, "HIT!")
    assert game.game_over and game.paused
    assert game.countdown == 0


def test_countdown_digit_is_drawn_by_strikes_renderer(monkeypatch):
    calls = []
    monkeypatch.setattr(
        d,
        "draw_countdown_timer",
        lambda image, n, age, **_kwargs: calls.append((image.shape, n, round(age, 3))),
    )

    game = d.DodgeballGame((640, 480))
    game.start(1)
    game.countdown = int(2.5 * d.FPS)
    camera = np.zeros((480, 640, 3), np.uint8)
    out = game.render_camera(camera)

    assert calls == [((480, 640, 3), 3, 0.5)]
    assert out is not camera  # draws on a copy, never the shared camera frame

    calls.clear()
    game.countdown = 0
    assert game.render_camera(camera) is camera and not calls  # no digit while playing

def test_countdown_emits_strike_countdown_ticks_once_per_digit(monkeypatch):
    from main.games.strike.screens import CountdownTick

    game = d.DodgeballGame((640, 480))
    game.start(1)
    _run_countdown(game)
    ticks: list[CountdownTick] = []
    monkeypatch.setattr(game, "_on_countdown_tick", ticks.append)

    game._lose_life(0, "HIT!")  # 5-second automatic restart
    _run_countdown(game)

    assert ticks == [CountdownTick(seconds_left=n) for n in (5, 4, 3, 2, 1)]


def test_countdown_digit_matches_strike_maths():
    game = d.DodgeballGame((640, 480))
    game.start(1)
    game.countdown = 3 * d.FPS
    assert game._countdown_digit() == (3, 0.0)  # never shows "4"
    game.countdown = int(2.5 * d.FPS)
    seconds_left, age = game._countdown_digit()
    assert seconds_left == 3 and age == pytest.approx(0.5)


def _knock_out(game, idx: int) -> None:
    while game.lives[idx] > 0 and not game.game_over:
        game._lose_life(idx, "HIT!")
        _run_countdown(game)


@pytest.mark.parametrize("players", [2, 3, 4])
def test_multiplayer_ends_only_when_one_player_is_left(players):
    game = d.DodgeballGame((640, 480))
    game.start(players)
    _run_countdown(game)
    survivor = players - 1
    for idx in range(players - 1):
        assert not game.game_over, f"ended with {players - idx} players still alive"
        _knock_out(game, idx)
        if idx < players - 2:
            assert game.hit_message == f"P{idx + 1} is OUT!"
            assert not game.paused  # play goes on
    assert game.game_over and game.paused
    assert game.hit_message == f"P{survivor + 1} WINS!"
    assert [i for i, n in enumerate(game.lives) if n > 0] == [survivor]


def test_knocked_out_player_is_ignored_while_the_rest_play_on():
    game = d.DodgeballGame((640, 480))
    game.start(3)
    _run_countdown(game)
    _knock_out(game, 1)
    assert game.lives[1] == 0 and not game.game_over
    # Out players can't lose more lives by leaving the frame.
    game.missing_frames[1] = d.OFFSCREEN_FRAMES
    game._check_offscreen([object(), None, object()])
    assert game.lives[1] == 0 and not game.game_over
