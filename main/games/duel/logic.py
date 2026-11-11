"""Pure duel rules. No camera, no pygame: feed it (timestamp, pose states) per frame.

Round flow:
  WAIT_START -> READY -> STEADY -> BANG -> ROUND_OVER -> WAIT_START ...
  The hit that takes a player's last life goes straight to MATCH_OVER, which first shows
  that round's result for `round_result_time`, then the winner.

A draw only counts once it has held for `draw_confirm_frames` consecutive frames; its
time is the capture timestamp of the first of those frames. A draw that started at or
before the BANG frame is early: that player can't score this round.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from main.pose import PoseState
from main.settings import DuelConfig

__all__ = [
    "Duel",
    "DuelConfig",
    "Phase",
    "RoundResult",
]


class Phase(Enum):
    WAIT_START = "wait_start"
    READY = "ready"
    STEADY = "steady"
    BANG = "bang"
    ROUND_OVER = "round_over"
    MATCH_OVER = "match_over"


@dataclass(frozen=True)
class RoundResult:
    winner: int | None
    reason: str  # "hit" | "tie" | "timeout" | "void"
    reaction_ms: tuple[float | None, float | None]
    early: tuple[bool, bool]


Event = tuple[str, "int | None"]  # e.g. ("bang", None), ("early", 0), ("hit", 1)


@dataclass
class _Debounce:
    run_start: float | None = None
    run_len: int = 0

    def feed(self, now: float, active: bool, needed: int) -> float | None:
        """Returns the run's start time on the frame the run becomes confirmed."""
        if not active:
            self.run_start, self.run_len = None, 0
            return None
        if self.run_len == 0:
            self.run_start = now
        self.run_len += 1
        return self.run_start if self.run_len == needed else None


@dataclass
class Duel:
    config: DuelConfig = field(default_factory=DuelConfig)
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        self.reset()

    # -- public state -----------------------------------------------------------------

    def reset(self) -> None:
        self.scores = [0, 0]
        self.last_result: RoundResult | None = None
        self.match_winner: int | None = None
        self.missing = (False, False)
        self._enter(Phase.WAIT_START, now=None)
        self._idle_since: float | None = None
        self._clear_round()

    def lives_left(self, i: int) -> int:
        return max(0, self.config.lives - self.scores[1 - i])

    def showing_final_round(self, now: float) -> bool:
        """MATCH_OVER starts by showing the deciding round's result, like ROUND_OVER."""
        return self.phase == Phase.MATCH_OVER and now - self.phase_start < self.config.round_result_time

    def can_restart(self, now: float) -> bool:
        cfg = self.config
        return (
            self.phase == Phase.MATCH_OVER
            and now - self.phase_start >= cfg.round_result_time + cfg.match_result_min_time
        )

    def start_progress(self, now: float) -> float:
        if self._idle_since is None:
            return 0.0
        return min(1.0, (now - self._idle_since) / self.config.start_hold)

    # -- per-frame update -------------------------------------------------------------

    def update(self, now: float, states: tuple[PoseState, PoseState]) -> list[Event]:
        events: list[Event] = []
        self.missing = tuple(s == PoseState.MISSING for s in states)
        present = not any(self.missing)
        cfg = self.config

        if self.phase == Phase.WAIT_START:
            if self._both_idle_held(now, states):
                self._start_round(now, events)

        elif self.phase in (Phase.READY, Phase.STEADY):
            if not present:
                self._enter(Phase.WAIT_START, now)
                self._idle_since = None
                self._clear_round()
                events.append(("abort", None))
                return events
            self._track_draws(now, states, events)
            if self.phase == Phase.READY and now - self.phase_start >= cfg.ready_to_steady:
                self._enter(Phase.STEADY, now)
                self.bang_at = now + self.rng.uniform(cfg.bang_delay_min, cfg.bang_delay_max)
                events.append(("steady", None))
            elif self.phase == Phase.STEADY and now >= self.bang_at:
                self._enter(Phase.BANG, now)
                self.bang_time = now
                events.append(("bang", None))
                if all(self.early):
                    self._finish(now, None, "void", events)

        elif self.phase == Phase.BANG:
            self._track_draws(now, states, events)
            self._maybe_resolve(now, events)

        elif self.phase == Phase.ROUND_OVER:
            if now - self.phase_start >= cfg.round_result_time:
                self._enter(Phase.WAIT_START, now)
                self._idle_since = None

        elif self.phase == Phase.MATCH_OVER:
            if self.can_restart(now) and self._both_idle_held(now, states):
                self.scores = [0, 0]
                self.match_winner = None
                self.last_result = None
                self._start_round(now, events)

        return events

    # -- internals --------------------------------------------------------------------

    def _enter(self, phase: Phase, now: float | None) -> None:
        self.phase = phase
        self.phase_start = now if now is not None else 0.0

    def _clear_round(self) -> None:
        self.bang_at: float | None = None
        self.bang_time: float | None = None
        self.early = [False, False]
        self.draw_time: list[float | None] = [None, None]
        self._debounce = [_Debounce(), _Debounce()]

    def _both_idle_held(self, now: float, states) -> bool:
        if all(s == PoseState.NEUTRAL for s in states):
            if self._idle_since is None:
                self._idle_since = now
            return now - self._idle_since >= self.config.start_hold
        self._idle_since = None
        return False

    def _start_round(self, now: float, events: list[Event]) -> None:
        self._clear_round()
        self._idle_since = None
        self._enter(Phase.READY, now)
        events.append(("ready", None))

    def _track_draws(self, now: float, states, events: list[Event]) -> None:
        for i in (0, 1):
            start = self._debounce[i].feed(
                now, states[i] == PoseState.DRAWN, self.config.draw_confirm_frames
            )
            if start is None or self.early[i] or self.draw_time[i] is not None:
                continue
            if self.bang_time is None or start <= self.bang_time:
                self.early[i] = True
                events.append(("early", i))
            else:
                self.draw_time[i] = start
                events.append(("draw", i))

    def _maybe_resolve(self, now: float, events: list[Event]) -> None:
        cfg = self.config
        eligible = [i for i in (0, 1) if not self.early[i]]
        drawn = [i for i in eligible if self.draw_time[i] is not None]
        if drawn:
            first = min(self.draw_time[i] for i in drawn)
            if len(drawn) == len(eligible) or now - first >= cfg.settle_time:
                if len(drawn) == 2 and abs(self.draw_time[0] - self.draw_time[1]) <= cfg.tie_window:
                    self._finish(now, None, "tie", events)
                else:
                    winner = min(drawn, key=lambda i: self.draw_time[i])
                    self._finish(now, winner, "hit", events)
                return
        if now - self.bang_time >= cfg.draw_timeout:
            self._finish(now, None, "timeout", events)

    def _finish(self, now: float, winner: int | None, reason: str, events: list[Event]) -> None:
        reaction = tuple(
            None if t is None else (t - self.bang_time) * 1000.0 for t in self.draw_time
        )
        self.last_result = RoundResult(winner, reason, reaction, tuple(self.early))
        if winner is not None:
            self.scores[winner] += 1
            events.append(("hit", winner))
            if self.scores[winner] >= self.config.lives:
                self.match_winner = winner
                self._enter(Phase.MATCH_OVER, now)
                events.append(("match_over", winner))
                return
        else:
            events.append((reason, None))
        self._enter(Phase.ROUND_OVER, now)
