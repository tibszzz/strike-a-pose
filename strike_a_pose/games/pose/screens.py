"""What the game shows and announces, as plain data.

This is the seam between game logic and presentation. `game.py` returns one
of the screen types below on every step and sends events to its listeners;
it never draws or plays anything itself. A renderer turns a screen into
pixels (`render_cv.py` is the only one so far), and anything that should
react to a moment in the game, such as sound, subscribes to events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Union

from .detector import Box
from .pose import Point, Pose


class Action(Enum):
    """What a player asked for with the keyboard."""

    CONFIRM = auto()
    QUIT = auto()


# --- screens -----------------------------------------------------------------


@dataclass(frozen=True)
class PlayerMarker:
    player: int  # 1 for the leftmost player
    box: Box


@dataclass(frozen=True)
class LobbyScreen:
    """Live feed while people get in frame. `markers` run left to right."""

    markers: tuple[PlayerMarker, ...]
    can_start: bool
    min_players: int
    max_players: int


@dataclass(frozen=True)
class CountdownScreen:
    round_number: int
    total_rounds: int
    target: Pose
    seconds_left: int


@dataclass(frozen=True)
class RetryScreen:
    """The snapshot found too few people, so the round will be replayed."""

    round_number: int
    total_rounds: int
    target: Pose
    found: int
    expected: int


@dataclass(frozen=True)
class PlayerResult:
    player: int
    joints: dict[str, Point]  # visible joints only, in snapshot pixels
    box: Box
    round_score: int
    total: int


@dataclass(frozen=True)
class ResultsScreen:
    round_number: int
    total_rounds: int
    target: Pose
    snapshot: object  # the camera frame; the game never looks inside it
    players: tuple[PlayerResult, ...]


@dataclass(frozen=True)
class Standing:
    place: int  # players with equal totals share a place
    player: int
    total: int


@dataclass(frozen=True)
class FinalScreen:
    standings: tuple[Standing, ...]  # best first


Screen = Union[LobbyScreen, CountdownScreen, RetryScreen, ResultsScreen, FinalScreen]


# --- events ------------------------------------------------------------------


@dataclass(frozen=True)
class CountdownTick:
    seconds_left: int


@dataclass(frozen=True)
class SnapshotTaken:
    round_number: int


@dataclass(frozen=True)
class RoundScored:
    round_number: int
    scores: tuple[int, ...]  # in player order: P1 first
    totals: tuple[int, ...]


@dataclass(frozen=True)
class GameOver:
    standings: tuple[Standing, ...]


Event = Union[CountdownTick, SnapshotTaken, RoundScored, GameOver]
