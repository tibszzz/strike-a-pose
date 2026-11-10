import random

import pytest

from strike_a_pose.games.duel.logic import Duel, DuelConfig, Phase
from strike_a_pose.pose import PoseState

H, D, M = PoseState.NEUTRAL, PoseState.DRAWN, PoseState.MISSING  # H = idle, not drawing
DT = 1 / 30


class FixedRng(random.Random):
    def __init__(self, delay: float):
        super().__init__()
        self.delay = delay

    def uniform(self, a, b):
        return self.delay


class Sim:
    """Drives a Duel at 30 fps with scripted pose states."""

    def __init__(self, bang_delay=2.0, **cfg):
        self.duel = Duel(DuelConfig(**cfg), FixedRng(bang_delay))
        self.t = 0.0
        self.events = []

    def step(self, p1, p2, frames=1):
        for _ in range(frames):
            self.t += DT
            self.events += self.duel.update(self.t, (p1, p2))

    def run_until(self, phase, p1, p2, max_frames=1000):
        for _ in range(max_frames):
            if self.duel.phase == phase:
                return
            self.step(p1, p2)
        raise AssertionError(f"never reached {phase}, stuck in {self.duel.phase}")

    def to_bang(self):
        self.run_until(Phase.READY, H, H)
        self.run_until(Phase.BANG, H, H)


def test_waits_for_both_idle_before_ready():
    s = Sim()
    s.step(H, H, frames=20)  # ~0.67 s, below the 1 s hold
    assert s.duel.phase == Phase.WAIT_START
    s.step(H, D)  # P2 raises a gun: timer resets
    s.step(H, H, frames=29)
    assert s.duel.phase == Phase.WAIT_START
    s.step(H, H, frames=2)
    assert s.duel.phase == Phase.READY
    assert ("ready", None) in s.events


def test_missing_player_blocks_start():
    s = Sim()
    s.step(H, M, frames=100)
    assert s.duel.phase == Phase.WAIT_START
    assert s.duel.missing == (False, True)


def test_ready_steady_bang_timing():
    s = Sim(bang_delay=2.5)
    s.run_until(Phase.READY, H, H)
    ready_t = s.t
    s.run_until(Phase.STEADY, H, H)
    assert s.t - ready_t == pytest.approx(1.5, abs=DT)
    steady_t = s.t
    s.run_until(Phase.BANG, H, H)
    assert s.t - steady_t == pytest.approx(2.5, abs=DT)


def test_faster_draw_wins_point_and_reaction_time():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=6)  # 200 ms
    s.step(D, H, frames=3)  # P1 draws
    s.step(D, D, frames=10)  # P2 draws much later
    r = s.duel.last_result
    assert r.winner == 0 and r.reason == "hit"
    assert r.reaction_ms[0] == pytest.approx(7 * DT * 1000, abs=1)
    assert s.duel.scores == [1, 0]
    assert s.duel.phase == Phase.ROUND_OVER


def test_simultaneous_draw_is_tie():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D, D, frames=5)
    assert s.duel.last_result.reason == "tie"
    assert s.duel.scores == [0, 0]


def test_one_frame_apart_is_tie_two_frames_is_not():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D, H)
    s.step(D, D, frames=5)
    assert s.duel.last_result.reason == "tie"

    s = Sim()
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D, H, frames=2)
    s.step(D, D, frames=5)
    assert s.duel.last_result.winner == 0


def test_early_draw_cannot_score_other_must_draw_after_bang():
    s = Sim()
    s.run_until(Phase.STEADY, H, H)
    s.step(D, H, frames=3)  # P1 jumps the gun
    assert ("early", 0) in s.events
    s.run_until(Phase.BANG, D, H)
    assert s.duel.phase == Phase.BANG  # round continues
    s.step(D, H, frames=10)
    assert s.duel.phase == Phase.BANG  # P1's raised arm doesn't score
    s.step(D, D, frames=3)
    r = s.duel.last_result
    assert r.winner == 1 and r.early == (True, False)
    assert r.reaction_ms[0] is None


def test_early_draw_and_other_never_draws_times_out():
    s = Sim()
    s.run_until(Phase.STEADY, H, H)
    s.step(D, H, frames=3)
    s.run_until(Phase.BANG, D, H)
    s.step(D, H, frames=int(3.0 / DT) + 2)
    assert s.duel.last_result.reason == "timeout"
    assert s.duel.scores == [0, 0]


def test_nobody_draws_times_out():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=int(3.0 / DT) + 2)
    assert s.duel.last_result.reason == "timeout"


def test_both_early_is_void_at_bang():
    s = Sim()
    s.run_until(Phase.STEADY, H, H)
    s.step(D, D, frames=3)
    s.run_until(Phase.ROUND_OVER, D, D)
    assert s.duel.last_result.reason == "void"
    assert s.duel.scores == [0, 0]


def test_draw_started_on_bang_frame_is_early():
    s = Sim()
    s.run_until(Phase.READY, H, H)
    s.run_until(Phase.STEADY, H, H)
    # step frame-by-frame, raising on the exact frame BANG fires
    while s.duel.phase != Phase.BANG:
        bang_frame = s.t + DT >= s.duel.bang_at
        s.step(D if bang_frame else H, H)
    assert s.duel.early == [False, False]
    s.step(D, H)
    assert s.duel.early[0] is True


def test_single_frame_twitch_is_ignored():
    s = Sim()
    s.run_until(Phase.STEADY, H, H)
    s.step(D, H)  # one-frame glitch
    s.step(H, H, frames=3)
    assert s.duel.early == [False, False]


def test_player_leaving_during_countdown_aborts():
    s = Sim()
    s.run_until(Phase.STEADY, H, H)
    s.step(H, M)
    assert s.duel.phase == Phase.WAIT_START
    assert ("abort", None) in s.events


def test_round_over_returns_to_wait_start():
    s = Sim()
    s.to_bang()
    s.step(D, H, frames=10)
    assert s.duel.phase == Phase.ROUND_OVER
    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert s.duel.phase == Phase.WAIT_START


def win_round(s, winner):
    s.run_until(Phase.WAIT_START, H, H)
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D if winner == 0 else H, D if winner == 1 else H, frames=10)


def test_three_lives_then_winner_screen_and_idle_restarts():
    s = Sim()
    win_round(s, 0)
    win_round(s, 1)
    win_round(s, 0)
    assert s.duel.phase == Phase.ROUND_OVER
    win_round(s, 0)
    assert s.duel.phase == Phase.MATCH_OVER
    assert s.duel.match_winner == 0 and s.duel.scores == [3, 1]
    assert ("match_over", 0) in s.events

    assert s.duel.lives_left(0) == 2 and s.duel.lives_left(1) == 0
    assert s.duel.showing_final_round(s.t)  # the deciding shot is shown first

    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert not s.duel.showing_final_round(s.t)
    assert s.duel.phase == Phase.MATCH_OVER  # then the winner screen, at least 3 s more
    assert not s.duel.can_restart(s.t)
    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert s.duel.can_restart(s.t)
    s.run_until(Phase.READY, H, H)
    assert s.duel.scores == [0, 0]


def test_lives_setting_changes_match_length():
    s = Sim(lives=1)
    win_round(s, 1)
    assert s.duel.phase == Phase.MATCH_OVER and s.duel.match_winner == 1
