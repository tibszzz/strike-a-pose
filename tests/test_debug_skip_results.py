"""`--debug` R skips to final results after gameplay has begun."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from main.games.dodgeball.dodgeball import DodgeballGame
from main.games.strike.play import StrikeGame
from main.games.strike.screens import FinalScreen
from main.pose.library import Person as LibPerson
from main.pose.library import Pose
from main.ready_up import Started
from main.settings import DodgeballConfig, StrikeConfig


def _lib_person(x: float = 200.0) -> LibPerson:
    joints = {
        "nose": (x, 100.0),
        "left_hip": (x - 20, 300.0),
        "right_hip": (x + 20, 300.0),
    }
    return LibPerson(
        joints=joints,
        confidence={name: 1.0 for name in joints},
        box=(x - 40, 40.0, x + 40, 320.0),
    )


def test_strike_debug_skip_to_final_after_start():
    poses = [Pose(name=f"p{i}", joints={"nose": (0.5, 0.2)}) for i in range(5)]
    game = StrikeGame(
        (640, 480),
        config=StrikeConfig(debug=True, min_players=1, max_players=2, rounds=2),
        poses=poses,
    )
    assert game.debug_skip_to_results() is False
    game._begin_from_started(Started(roster=(_lib_person(),)), timestamp=1.0)
    assert game._in_ready_up is False
    assert game.debug_skip_to_results() is True
    assert isinstance(game._screen, FinalScreen)
    assert game._in_end_screen()


def test_dodgeball_debug_skip_to_game_over_after_start():
    pygame.init()
    game = DodgeballGame((640, 480), config=DodgeballConfig(debug=True))
    assert game.debug_skip_to_results() is False
    game.start(2, seed_x=[160.0, 480.0])
    assert game.game_over is False
    assert game.debug_skip_to_results() is True
    assert game.game_over is True
    assert game.lives[0] > 0
    assert game.lives[1] == 0
