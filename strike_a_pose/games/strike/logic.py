"""The game itself: phases, timing and scores.

The game is driven from outside. Each call to `step` passes in the current
time, whether a player confirmed, and (when `wants_people` asked for them) the
camera frame with the people found in it. It returns a description of the
screen to show. Nothing here reads a clock, a camera or a keyboard, and
nothing draws.
"""

from __future__ import annotations

import math
import random
from enum import Enum, auto
from typing import Callable, Sequence

from strike_a_pose.config import Config
from strike_a_pose.pose import Person, Pose, left_to_right, select_players

from .scoring import round_score, score_pose
from .screens import (
    CountdownScreen,
    CountdownTick,
    Event,
    FinalScreen,
    GameOver,
    LobbyScreen,
    PlayerMarker,
    PlayerResult,
    ResultsScreen,
    RetryScreen,
    RoundScored,
    Screen,
    SnapshotTaken,
    Standing,
)


class _Phase(Enum):
    LOBBY = auto()
    COUNTDOWN = auto()
    RETRY = auto()
    RESULTS = auto()
    FINAL = auto()


def rank(totals: Sequence[int]) -> tuple[Standing, ...]:
    """Standings, best first. Equal totals share a place: 1, 1, 3."""
    standings = [
        Standing(
            place=1 + sum(other > total for other in totals),
            player=index + 1,
            total=total,
        )
        for index, total in enumerate(totals)
    ]
    return tuple(sorted(standings, key=lambda standing: standing.place))


class Game:
    def __init__(
        self,
        config: Config,
        poses: Sequence[Pose],
        rng: random.Random | None = None,
    ) -> None:
        if len(poses) < config.rounds:
            raise ValueError(
                f"a game needs {config.rounds} different poses, "
                f"but only {len(poses)} were loaded"
            )
        self._config = config
        self._poses = list(poses)
        self._rng = rng or random.Random()
        self._listeners: list[Callable[[Event], None]] = []

        self._phase = _Phase.LOBBY
        self._lobby_people: list[Person] = []
        self._player_count = 0
        self._targets: list[Pose] = []
        self._round_index = 0
        self._totals: list[int] = []
        self._deadline = 0.0
        self._last_tick: int | None = None
        self._found = 0
        self._results: ResultsScreen | None = None

    def subscribe(self, listener: Callable[[Event], None]) -> None:
        """Have `listener` called with every event the game announces."""
        self._listeners.append(listener)

    def wants_people(self, now: float) -> bool:
        """Whether the next `step` needs the frame and the people in it.

        True all through the lobby, and at the moment a snapshot is due.
        """
        if self._phase is _Phase.LOBBY:
            return True
        return self._phase is _Phase.COUNTDOWN and now >= self._deadline

    def step(
        self,
        now: float,
        confirm: bool = False,
        frame: object = None,
        people: Sequence[Person] | None = None,
    ) -> Screen:
        """Advance the game to `now` and return the screen to show."""
        if self._phase is _Phase.LOBBY:
            return self._step_lobby(now, confirm, people)
        if self._phase is _Phase.COUNTDOWN:
            return self._step_countdown(now, frame, people)
        if self._phase is _Phase.RETRY:
            return self._step_retry(now, confirm)
        if self._phase is _Phase.RESULTS:
            return self._step_results(now, confirm)
        return self._step_final(now, confirm)

    # --- lobby ---------------------------------------------------------------

    def _step_lobby(
        self, now: float, confirm: bool, people: Sequence[Person] | None
    ) -> Screen:
        if people is not None:
            self._lobby_people = left_to_right(people)
        count = len(self._lobby_people)
        can_start = self._config.min_players <= count <= self._config.max_players

        if confirm and can_start:
            self._player_count = count
            self._totals = [0] * count
            self._targets = self._rng.sample(self._poses, self._config.rounds)
            self._round_index = 0
            return self._start_countdown(now)

        return LobbyScreen(
            markers=tuple(
                PlayerMarker(player=index + 1, box=person.box)
                for index, person in enumerate(self._lobby_people)
            ),
            can_start=can_start,
            min_players=self._config.min_players,
            max_players=self._config.max_players,
        )

    # --- countdown and snapshot ----------------------------------------------

    def _start_countdown(self, now: float) -> Screen:
        self._phase = _Phase.COUNTDOWN
        self._deadline = now + self._config.countdown_seconds
        self._last_tick = None
        return self._step_countdown(now, None, None)

    def _step_countdown(
        self, now: float, frame: object, people: Sequence[Person] | None
    ) -> Screen:
        remaining = self._deadline - now
        if remaining > 0:
            # Capped because float error can leave `remaining` a hair above
            # the full countdown on the first step, which would show "6".
            seconds_left = min(
                math.ceil(remaining), math.ceil(self._config.countdown_seconds)
            )
            if seconds_left != self._last_tick:
                self._last_tick = seconds_left
                self._emit(CountdownTick(seconds_left=seconds_left))
            return CountdownScreen(
                round_number=self._round_number,
                total_rounds=self._config.rounds,
                target=self._target,
                seconds_left=seconds_left,
            )

        if people is None:
            raise ValueError(
                "the snapshot is due: call wants_people() first, then pass the "
                "frame and the people found in it"
            )
        return self._take_snapshot(frame, people)

    def _take_snapshot(self, frame: object, people: Sequence[Person]) -> Screen:
        self._emit(SnapshotTaken(round_number=self._round_number))

        players = select_players(people, self._player_count)
        if players is None:
            self._phase = _Phase.RETRY
            self._found = len(people)
            return self._retry_screen()

        results = []
        for index, person in enumerate(players):
            visible = person.visible_joints(self._config.joint_confidence)
            score = round_score(
                score_pose(self._target.joints, visible, self._config.strictness_degrees)
            )
            self._totals[index] += score
            results.append(
                PlayerResult(
                    player=index + 1,
                    joints=visible,
                    box=person.box,
                    round_score=score,
                    total=self._totals[index],
                )
            )

        self._phase = _Phase.RESULTS
        self._results = ResultsScreen(
            round_number=self._round_number,
            total_rounds=self._config.rounds,
            target=self._target,
            snapshot=frame,
            players=tuple(results),
        )
        self._emit(
            RoundScored(
                round_number=self._round_number,
                scores=tuple(result.round_score for result in results),
                totals=tuple(self._totals),
            )
        )
        return self._results

    # --- retry, results, final -----------------------------------------------

    def _step_retry(self, now: float, confirm: bool) -> Screen:
        if confirm:
            return self._start_countdown(now)
        return self._retry_screen()

    def _retry_screen(self) -> RetryScreen:
        return RetryScreen(
            round_number=self._round_number,
            total_rounds=self._config.rounds,
            target=self._target,
            found=self._found,
            expected=self._player_count,
        )

    def _step_results(self, now: float, confirm: bool) -> Screen:
        assert self._results is not None
        if not confirm:
            return self._results
        if self._round_number < self._config.rounds:
            self._round_index += 1
            return self._start_countdown(now)
        self._phase = _Phase.FINAL
        self._emit(GameOver(standings=rank(self._totals)))
        return FinalScreen(standings=rank(self._totals))

    def _step_final(self, now: float, confirm: bool) -> Screen:
        if confirm:
            self._phase = _Phase.LOBBY
            self._lobby_people = []
            return self._step_lobby(now, False, None)
        return FinalScreen(standings=rank(self._totals))

    # --- helpers -------------------------------------------------------------

    @property
    def _round_number(self) -> int:
        return self._round_index + 1

    @property
    def _target(self) -> Pose:
        return self._targets[self._round_index]

    def _emit(self, event: Event) -> None:
        for listener in self._listeners:
            listener(event)
