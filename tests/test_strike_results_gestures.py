"""Strike results screen no longer needs gestures; ready-up / end still do."""

from __future__ import annotations

from main.games.strike.play import StrikeGame
from main.games.strike.screens import PlayerResult, ResultsScreen
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose.library import Pose


def _pose() -> Pose:
    return Pose(name="t", joints={"nose": (0.5, 0.2)})


def _results(*, idle: bool) -> ResultsScreen:
    players = (
        PlayerResult(1, {}, (0.0, 0.0, 100.0, 200.0), 50, 50),
        PlayerResult(2, {}, (200.0, 0.0, 300.0, 200.0), 40, 40),
    )
    return ResultsScreen(
        round_number=1,
        total_rounds=5,
        target=_pose(),
        snapshot=object(),
        players=players,
        display_scores=(50, 40) if idle else (12, 88),
        idle=idle,
        advance_remaining_s=5.0 if idle else None,
        advance_progress=0.0 if idle else None,
    )


def test_strike_tracks_one_gesture_hand_outside_ready_up():
    game = StrikeGame((640, 480))
    game._in_ready_up = False
    assert game.gesture_hands == NAV_GESTURE_HANDS


def test_wants_gestures_false_on_results_even_when_idle():
    game = StrikeGame((640, 480))
    game._in_ready_up = False
    game._screen = _results(idle=False)
    assert game.wants_gestures is False
    game._screen = _results(idle=True)
    assert game.wants_gestures is False


def test_wants_gestures_on_final_screen():
    from main.games.strike.screens import FinalScreen, Standing

    game = StrikeGame((640, 480))
    game._in_ready_up = False
    game._screen = FinalScreen(standings=(Standing(place=1, player=1, total=3),))
    assert game.wants_gestures is True
    assert game.gesture_hands == NAV_GESTURE_HANDS


def test_wants_gestures_during_ready_up():
    game = StrikeGame((640, 480))
    assert game._in_ready_up is True
    assert game.wants_gestures is True
    assert game.gesture_hands == game._config.max_players * 2
