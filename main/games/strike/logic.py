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
from dataclasses import replace
from enum import Enum, auto
from typing import Callable, Sequence
from main.settings import StrikeConfig
from main.pose.library import Person, Pose, left_to_right
from main.ready_up import match_roster_slots
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
    RoundScored,
    ScoreRevealLocked,
    ScoreRevealTick,
    Screen,
    SnapshotTaken,
    Standing,
)


class _Phase(Enum):
    LOBBY = auto()
    COUNTDOWN = auto()
    RESULTS = auto()
    FINAL = auto()


# Placeholder box for a roster seat with nobody in frame (score stack anchor).
_ABSENT_HALF_W = 100.0
_ABSENT_TOP = 120.0
_ABSENT_BOTTOM = 520.0


def _absent_box(seed_x: float) -> tuple[float, float, float, float]:
    return (
        seed_x - _ABSENT_HALF_W,
        _ABSENT_TOP,
        seed_x + _ABSENT_HALF_W,
        _ABSENT_BOTTOM,
    )


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


def _copy_snapshot(frame: object) -> object:
    copy = getattr(frame, "copy", None)
    return copy() if callable(copy) else frame


# Distinct placeholder scores so padded seats reveal in a stable, varied order.
_DEBUG_PAD_SCORES = (15, 40, 65, 90)


def _shift_joints(
    joints: dict[str, tuple[float, float]], dx: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y) for name, (x, y) in joints.items()}


def _shift_box(
    box: tuple[float, float, float, float], dx: float
) -> tuple[float, float, float, float]:
    return (box[0] + dx, box[1], box[2] + dx, box[3])


def pad_results_to_max(
    players: Sequence[PlayerResult],
    *,
    max_players: int,
    totals: list[int],
) -> tuple[PlayerResult, ...]:
    """Fill empty seats with cloned skeletons so debug reveals exercise max_players."""
    if len(players) >= max_players:
        return tuple(players)

    template = players[0]
    template_cx = (template.box[0] + template.box[2]) / 2
    width = template.box[2] - template.box[0]
    gap = width * 1.2
    rightmost = max(player.box[2] for player in players)
    padded = list(players)

    for index in range(len(players), max_players):
        center = rightmost + gap * (index - len(players) + 0.5)
        dx = center - template_cx
        score = _DEBUG_PAD_SCORES[index % len(_DEBUG_PAD_SCORES)]
        totals[index] += score
        padded.append(
            PlayerResult(
                player=index + 1,
                joints=_shift_joints(template.joints, dx),
                box=_shift_box(template.box, dx),
                round_score=score,
                total=totals[index],
            )
        )
    return tuple(padded)


class Game:
    def __init__(
        self,
        config: StrikeConfig,
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
        self._roster_seed_x: list[float] = []
        self._player_count = 0
        self._targets: list[Pose] = []
        self._round_index = 0
        self._totals: list[int] = []
        self._round_scores: list[list[int]] = []
        self._deadline = 0.0
        self._last_tick: int | None = None
        self._results: ResultsScreen | None = None
        self._results_at = 0.0
        self._last_reveal_flash: int | None = None

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
            self._roster_seed_x = [person.center_x for person in self._lobby_people]
            seats = (
                self._config.max_players if self._config.debug else count
            )
            self._totals = [0] * seats
            self._round_scores = [[] for _ in range(seats)]
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
            duration = self._config.countdown_seconds
            elapsed = max(0.0, duration - remaining)
            return CountdownScreen(
                round_number=self._round_number,
                total_rounds=self._config.rounds,
                target=self._target,
                seconds_left=seconds_left,
                elapsed=elapsed,
                digit_age=max(0.0, seconds_left - remaining),
            )

        if people is None:
            raise ValueError(
                "the snapshot is due: call wants_people() first, then pass the "
                "frame and the people found in it"
            )
        return self._take_snapshot(now, frame, people)

    def _take_snapshot(self, now: float, frame: object, people: Sequence[Person]) -> Screen:
        self._emit(SnapshotTaken(round_number=self._round_number))

        slots = match_roster_slots(people, self._roster_seed_x)
        results = []
        for index, person in enumerate(slots):
            if person is None:
                results.append(
                    PlayerResult(
                        player=index + 1,
                        joints={},
                        box=_absent_box(self._roster_seed_x[index]),
                        round_score=0,
                        total=self._totals[index],
                    )
                )
                continue
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

        scored: tuple[PlayerResult, ...] = tuple(results)
        if self._config.debug:
            scored = pad_results_to_max(
                scored,
                max_players=self._config.max_players,
                totals=self._totals,
            )

        for result in scored:
            if 0 < result.player <= len(self._round_scores):
                self._round_scores[result.player - 1].append(result.round_score)

        self._phase = _Phase.RESULTS
        self._results_at = now
        self._last_reveal_flash = -1
        self._results = ResultsScreen(
            round_number=self._round_number,
            total_rounds=self._config.rounds,
            target=self._target,
            snapshot=_copy_snapshot(frame),
            players=scored,
            display_scores=tuple(0 for _ in scored),
            idle=False,
            holding=True,
        )
        self._emit(
            RoundScored(
                round_number=self._round_number,
                scores=tuple(result.round_score for result in scored),
                totals=tuple(self._totals),
            )
        )
        # Score scramble / drumroll wait for results_hold_s; kick off if hold is 0.
        self._advance_score_reveal(now)
        return self._results

    # --- results, final ------------------------------------------------------

    def _step_results(self, now: float, confirm: bool) -> Screen:
        assert self._results is not None
        if not self._results.idle:
            self._advance_score_reveal(now)
            # Lock frame (and every scramble frame) ignores confirm — no skip.
            return self._results
        remaining = self._results_advance_remaining(now)
        if remaining > 0:
            self._results = replace(
                self._results,
                advance_remaining_s=remaining,
                advance_progress=self._results_advance_progress(remaining),
            )
            return self._results
        if self._round_number < self._config.rounds:
            self._round_index += 1
            return self._start_countdown(now)
        self._phase = _Phase.FINAL
        self._emit(GameOver(standings=rank(self._totals)))
        return self._final_screen()

    def _results_lock_at(self) -> float:
        return (
            self._results_at
            + self._config.results_hold_s
            + self._config.results_reveal_s
        )

    def _results_advance_remaining(self, now: float) -> float:
        return self._config.results_advance_s - (now - self._results_lock_at())

    def _results_advance_progress(self, remaining: float) -> float:
        duration = self._config.results_advance_s
        if duration <= 0:
            return 1.0
        elapsed = duration - remaining
        return min(1.0, max(0.0, elapsed / duration))

    def _advance_score_reveal(self, now: float) -> None:
        assert self._results is not None
        elapsed = now - self._results_at
        hold = self._config.results_hold_s
        if elapsed < hold:
            return
        reveal_elapsed = elapsed - hold
        if reveal_elapsed >= self._config.results_reveal_s:
            finals = tuple(player.round_score for player in self._results.players)
            self._results = replace(
                self._results,
                display_scores=finals,
                idle=True,
                holding=False,
                advance_remaining_s=self._config.results_advance_s,
                advance_progress=0.0,
            )
            self._emit(ScoreRevealLocked(scores=finals))
            return

        # Epsilon keeps exact 1/hz boundaries from flooring down (e.g. 0.1*10).
        flash_index = math.floor(
            reveal_elapsed * self._config.results_reveal_hz + 1e-9
        )
        if flash_index == self._last_reveal_flash:
            return
        self._last_reveal_flash = flash_index
        display_scores = self._roll_display_scores(self._results.players)
        self._results = replace(
            self._results, display_scores=display_scores, holding=False
        )
        self._emit(ScoreRevealTick(scores=display_scores))

    def _roll_display_scores(self, players: Sequence[PlayerResult]) -> tuple[int, ...]:
        """Random 0–100 per player, excluding each player's true round score."""
        return tuple(
            self._roll_scramble_score(player.round_score) for player in players
        )

    def _roll_scramble_score(self, final: int) -> int:
        choices = [n for n in range(101) if n != final]
        return self._rng.choice(choices)

    def debug_force_final(self) -> FinalScreen | None:
        """Debug only: jump to FINAL standings. None if still in lobby."""
        if self._phase is _Phase.LOBBY:
            return None
        seats = max(1, self._player_count, len(self._totals))
        if len(self._totals) < seats:
            self._totals = list(self._totals) + [0] * (seats - len(self._totals))
        if len(self._round_scores) < seats:
            self._round_scores = list(self._round_scores) + [
                [] for _ in range(seats - len(self._round_scores))
            ]
        if self._totals and max(self._totals) == 0:
            self._totals[0] = 1
        self._phase = _Phase.FINAL
        screen = self._final_screen()
        self._emit(GameOver(standings=screen.standings))
        return screen

    def _step_final(self, now: float, confirm: bool) -> Screen:
        if confirm:
            self._phase = _Phase.LOBBY
            self._lobby_people = []
            self._roster_seed_x = []
            return self._step_lobby(now, False, None)
        return self._final_screen()

    def _final_screen(self) -> FinalScreen:
        return FinalScreen(
            standings=rank(self._totals),
            round_scores=tuple(tuple(scores) for scores in self._round_scores),
            total_rounds=self._config.rounds,
        )

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
