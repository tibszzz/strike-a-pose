import random

import pytest

from main.games.duel.logic import Duel, DuelConfig, Phase
from main.pose import PoseState

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
        cfg.setdefault("start_delay", 0.0)
        self.duel = Duel(DuelConfig(**cfg), FixedRng(bang_delay))
        self.t = 0.0
        self.events = []

    def step(self, p1, p2, frames=1):
        for _ in range(frames):
            self.t += DT
            self.events += self.duel.update(self.t, (p1, p2))

    def request_start(self):
        self.t += DT
        self.events += self.duel.request_start(self.t)

    def run_until(self, phase, p1, p2, max_frames=1000):
        for _ in range(max_frames):
            if self.duel.phase == phase:
                return
            if self.duel.phase == Phase.WAIT_START and phase != Phase.WAIT_START:
                self.request_start()
                continue
            if (
                self.duel.phase == Phase.MATCH_OVER
                and phase == Phase.READY
                and self.duel.can_restart(self.t)
            ):
                self.request_start()
                continue
            self.step(p1, p2)
        raise AssertionError(f"never reached {phase}, stuck in {self.duel.phase}")

    def to_bang(self):
        self.run_until(Phase.READY, H, H)
        self.run_until(Phase.BANG, H, H)

    def finish_replay(self, p1=H, p2=H):
        while self.duel.phase == Phase.REPLAY:
            self.step(p1, p2)


def test_request_start_begins_ready():
    s = Sim()
    s.step(H, H, frames=20)
    assert s.duel.phase == Phase.WAIT_START
    s.request_start()
    assert s.duel.phase == Phase.READY
    assert ("ready", None) in s.events


def test_idle_hold_starts_round_without_request_start():
    """Between rounds / after abort: both idle for start_hold begins READY."""
    s = Sim(start_hold=0.5)
    s.step(H, H, frames=10)  # ~0.33s — not enough
    assert s.duel.phase == Phase.WAIT_START
    s.step(H, H, frames=20)  # past 0.5s
    assert s.duel.phase == Phase.READY
    assert ("ready", None) in s.events


def test_drawn_pose_blocks_idle_start():
    s = Sim(start_hold=0.3)
    s.step(D, H, frames=40)
    assert s.duel.phase == Phase.WAIT_START


def test_debug_solo_starts_against_idle_ghost():
    s = Sim(debug=True)
    s.request_start()
    s.step(H, M)  # ghost fills missing opponent after start
    assert s.duel.phase == Phase.READY
    assert s.duel.missing == (False, False)
    assert ("ready", None) in s.events


def test_debug_solo_draw_beats_ghost():
    s = Sim(debug=True)
    s.run_until(Phase.READY, H, M)
    s.run_until(Phase.BANG, H, M)
    s.step(H, M, frames=6)
    s.step(D, M, frames=10)
    r = s.duel.last_result
    assert r.winner == 0 and r.reason == "hit"
    assert s.duel.scores == [1, 0]


def test_debug_solo_leaving_aborts_countdown():
    s = Sim(debug=True)
    s.run_until(Phase.STEADY, H, M)
    s.step(M, M)
    assert s.duel.phase == Phase.WAIT_START
    assert ("abort", None) in s.events


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
    assert s.duel.phase == Phase.REPLAY
    s.finish_replay()
    assert s.duel.phase == Phase.ROUND_OVER


def test_timeout_skips_replay():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=int(3.0 / DT) + 2)
    assert s.duel.last_result.reason == "timeout"
    assert s.duel.phase == Phase.ROUND_OVER


def test_same_frame_draw_is_never_a_tie():
    winners = set()
    for seed in range(20):
        s = Sim()
        s.duel.rng.seed(seed)
        s.to_bang()
        s.step(H, H, frames=6)
        s.step(D, D, frames=5)
        r = s.duel.last_result
        assert r.reason == "hit" and r.winner in (0, 1)
        assert sum(s.duel.scores) == 1
        assert s.duel.phase == Phase.REPLAY
        winners.add(r.winner)
    assert winners == {0, 1}  # coin flip, not a fixed side


def test_one_frame_faster_wins():
    s = Sim()
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D, H)
    s.step(D, D, frames=5)
    assert s.duel.last_result.winner == 0

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
    assert s.duel.phase == Phase.REPLAY
    s.finish_replay()
    assert s.duel.phase == Phase.ROUND_OVER
    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert s.duel.phase == Phase.WAIT_START


def win_round(s, winner):
    s.run_until(Phase.WAIT_START, H, H)
    s.to_bang()
    s.step(H, H, frames=6)
    s.step(D if winner == 0 else H, D if winner == 1 else H, frames=10)
    s.finish_replay()


def test_three_lives_then_winner_screen_and_request_start_restarts():
    s = Sim()
    win_round(s, 0)
    win_round(s, 1)
    win_round(s, 0)
    assert s.duel.phase == Phase.ROUND_OVER
    win_round(s, 0)
    assert s.duel.phase == Phase.MATCH_OVER
    assert s.duel.match_winner == 0 and s.duel.scores == [3, 1]
    assert ("match_over", 0) not in s.events  # deferred until the winner screen

    assert s.duel.lives_left(0) == 2 and s.duel.lives_left(1) == 0
    assert s.duel.showing_final_round(s.t)  # the deciding shot is shown first

    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert not s.duel.showing_final_round(s.t)
    assert ("match_over", 0) in s.events
    assert s.duel.phase == Phase.MATCH_OVER  # then the winner screen, at least 3 s more
    assert not s.duel.can_restart(s.t)
    s.step(H, H, frames=int(3.0 / DT) + 1)
    assert s.duel.can_restart(s.t)
    s.request_start()
    assert s.duel.phase == Phase.READY
    assert s.duel.scores == [0, 0]


def test_lives_setting_changes_match_length():
    s = Sim(lives=1)
    win_round(s, 1)
    assert s.duel.phase == Phase.MATCH_OVER and s.duel.match_winner == 1
    assert ("match_over", 1) not in s.events


def test_replay_duration_uses_speed_and_freeze():
    s = Sim(replay_speed=0.25, replay_freeze=1.0)
    s.to_bang()
    bang = s.duel.bang_time
    s.step(H, H, frames=6)
    s.step(D, H, frames=2)  # confirm draw
    s.run_until(Phase.REPLAY, D, H)
    first = min(t for t in s.duel.draw_time if t is not None)
    expected = (first - bang) / 0.25 + 1.0
    assert s.duel.replay_until - s.duel.phase_start == pytest.approx(expected, abs=DT)


def test_start_delay_ignores_poses_then_starts():
    """The ready-up fist (arm still up) during the countdown is not an early draw."""
    s = Sim(start_delay=5.0)
    s.request_start()
    assert s.duel.phase == Phase.INTRO
    assert ("ready", None) not in s.events
    s.step(D, D, frames=int(4.9 / DT))  # arms up the whole countdown
    assert s.duel.phase == Phase.INTRO
    assert s.duel.intro_left(s.t) > 0
    s.step(H, H, frames=6)
    assert s.duel.phase == Phase.READY
    assert ("ready", None) in s.events
    assert ("early", 0) not in s.events and ("early", 1) not in s.events
    assert s.duel.early == [False, False]


def test_start_delay_also_applies_to_rematch():
    s = Sim(start_delay=5.0, lives=1, round_result_time=0.1, match_result_min_time=0.1)
    s.request_start()
    s.step(H, H, frames=int(5.0 / DT) + 2)
    s.run_until(Phase.BANG, H, H)
    s.step(H, H, frames=6)
    s.step(D, H, frames=5)
    s.finish_replay()
    s.run_until(Phase.MATCH_OVER, H, H)
    s.step(H, H, frames=10)
    assert s.duel.can_restart(s.t)
    s.request_start()
    assert s.duel.phase == Phase.INTRO
