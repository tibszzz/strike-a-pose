"""What the game shows and announces, as plain data.

This is the seam between game logic and presentation. `logic.py` returns one
of the screen types below on every step and sends events to its listeners;
it never draws or plays anything itself. A renderer turns a screen into
pixels (`game.py` is the only one so far), and anything that should
react to a moment in the game, such as sound, subscribes to events.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Union

from main.pose.library import Box, Point, Pose


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
    elapsed: float
    digit_age: float


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
    display_scores: tuple[int, ...]  # parallel to players; scrambled until lock
    idle: bool  # True once the score reveal locks; auto-advance timer runs
    holding: bool = False  # True during the post-snapshot beat before scramble
    # Seconds until auto-advance while idle; None before the reveal locks.
    advance_remaining_s: float | None = None
    # 0–1 elapsed fraction of the advance wait; drives the results progress bar.
    advance_progress: float | None = None


@dataclass(frozen=True)
class Standing:
    place: int  # players with equal totals share a place
    player: int
    total: int


@dataclass(frozen=True)
class FinalScreen:
    standings: tuple[Standing, ...]  # best first
    # Per-round scores per seat (index 0 = P1), in round order; feeds the points table.
    round_scores: tuple[tuple[int, ...], ...] = ()
    total_rounds: int = 0


Screen = Union[LobbyScreen, CountdownScreen, ResultsScreen, FinalScreen]


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
class ScoreRevealTick:
    """One scramble flash during the results score reveal."""

    scores: tuple[int, ...]  # in player order: P1 first


@dataclass(frozen=True)
class ScoreRevealLocked:
    """Final scores landed; auto-advance timer starts."""

    scores: tuple[int, ...]  # in player order: P1 first


@dataclass(frozen=True)
class GameOver:
    standings: tuple[Standing, ...]


Event = Union[
    CountdownTick,
    SnapshotTaken,
    RoundScored,
    ScoreRevealTick,
    ScoreRevealLocked,
    GameOver,
]
