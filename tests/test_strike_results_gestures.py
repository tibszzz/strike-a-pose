"""Strike results-screen gesture recognition: one hand, delayed start."""

from __future__ import annotations

import numpy as np

from main.games.strike.game import overlay_results_hold
from main.games.strike.play import StrikeGame
from main.games.strike.screens import PlayerResult, ResultsScreen
from main.nav import GestureSnapshot, HandGesture, NAV_GESTURE_HANDS
from main.pose.library import Pose


def _pose() -> Pose:
    return Pose(name="t", joints={"nose": (0.5, 0.2)})


def _results(*, idle: bool) -> ResultsScreen:
    return ResultsScreen(
        round_number=1,
        total_rounds=5,
        target=_pose(),
        snapshot=object(),
        players=(
            PlayerResult(1, {}, (0.0, 0.0, 100.0, 200.0), 50, 50),
            PlayerResult(2, {}, (200.0, 0.0, 300.0, 200.0), 40, 40),
        ),
        idle=idle,
    )


def test_strike_tracks_one_gesture_hand_outside_ready_up():
    game = StrikeGame((640, 480))
    game._in_ready_up = False
    assert game.gesture_hands == NAV_GESTURE_HANDS


def test_wants_gestures_only_when_results_are_idle():
    game = StrikeGame((640, 480))
    game._in_ready_up = False
    game._screen = _results(idle=False)
    assert game.wants_gestures is False
    game._screen = _results(idle=True)
    assert game.wants_gestures is True
    game._screen = object()
    assert game.wants_gestures is False


def test_wants_gestures_during_ready_up():
    game = StrikeGame((640, 480))
    assert game._in_ready_up is True
    assert game.wants_gestures is True
    assert game.gesture_hands == game._config.max_players * 2


def test_overlay_draws_only_the_primary_hand(monkeypatch):
    drawn: list[tuple[tuple[float, float], ...]] = []

    def fake_draw(_canvas, landmarks, _transform, _color):
        drawn.append(tuple(landmarks))

    monkeypatch.setattr(
        "main.games.strike.game.draw_hand_skeleton", fake_draw
    )

    primary = ((50.0, 60.0), (55.0, 50.0), (60.0, 45.0))
    secondary = ((250.0, 60.0), (255.0, 50.0), (260.0, 45.0))
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=primary,
        hand_box=(40.0, 40.0, 70.0, 80.0),
        hands=(
            HandGesture("Thumb_Up", 0.95, (40.0, 40.0, 70.0, 80.0), primary),
            HandGesture("Victory", 0.8, (240.0, 40.0, 270.0, 80.0), secondary),
        ),
    )
    canvas = np.zeros((720, 1280, 3), dtype=np.uint8)
    overlay_results_hold(
        canvas,
        0.0,
        final_round=False,
        snap=snap,
        frame_size=(640, 480),
        players=(),
    )
    assert drawn == [primary]
