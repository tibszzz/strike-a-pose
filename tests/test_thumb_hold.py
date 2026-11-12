"""Unit tests for the shared Thumb_Up hold tracker."""

import pytest

from main.nav import GestureSnapshot, ThumbHoldTracker, effective_label, hand_anchor


def test_effective_label_respects_min_score():
    snap = GestureSnapshot(label="Thumb_Up", score=0.4)
    assert effective_label(snap, 0.5) is None
    assert effective_label(snap, 0.4) == "Thumb_Up"


def test_hand_anchor_prefers_wrist_landmark():
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=1.0,
        landmarks=((10.0, 20.0), (30.0, 40.0)),
        hand_box=(0.0, 0.0, 50.0, 50.0),
    )
    assert hand_anchor(snap) == (10.0, 20.0)
    assert hand_anchor(GestureSnapshot(label=None, score=0.0, hand_box=(0.0, 0.0, 40.0, 20.0))) == (
        20.0,
        10.0,
    )


def test_thumb_hold_fires_after_duration():
    tracker = ThumbHoldTracker(hold_s=1.5, min_score=0.5)
    snap = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),))
    assert tracker.update(snap, 1.0, frame_size=(640, 480)) is False
    assert tracker.progress == 0.0
    assert tracker.update(snap, 2.0, frame_size=(640, 480)) is False
    assert tracker.progress == pytest.approx(1.0 / 1.5)
    assert tracker.update(snap, 2.5, frame_size=(640, 480)) is True
    assert tracker.fired is True
    assert tracker.update(snap, 3.0, frame_size=(640, 480)) is False


def test_hold_tracker_accepts_closed_fist_label():
    tracker = ThumbHoldTracker(hold_s=0.5, label="Closed_Fist")
    fist = GestureSnapshot(label="Closed_Fist", score=1.0, landmarks=((100.0, 200.0),))
    thumb = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),))
    assert tracker.update(thumb, 1.0, frame_size=(640, 480)) is False
    assert not tracker.active
    assert tracker.update(fist, 1.0, frame_size=(640, 480)) is False
    assert tracker.update(fist, 1.5, frame_size=(640, 480)) is True


def test_thumb_hold_resets_when_disarmed_or_released():
    tracker = ThumbHoldTracker(hold_s=1.0)
    snap = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),))
    tracker.update(snap, 1.0, frame_size=(640, 480))
    tracker.update(snap, 1.5, frame_size=(640, 480))
    assert tracker.active

    assert tracker.update(snap, 1.6, frame_size=(640, 480), armed=False) is False
    assert not tracker.active

    tracker.update(snap, 2.0, frame_size=(640, 480))
    assert tracker.update(GestureSnapshot(label=None, score=0.0), 2.1, frame_size=(640, 480)) is False
    assert not tracker.active


def test_thumb_hold_ignores_other_hand_until_release():
    tracker = ThumbHoldTracker(hold_s=1.5)
    near = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),))
    far = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=((500.0, 200.0),))

    tracker.update(near, 1.0, frame_size=(640, 480))
    tracker.update(near, 2.0, frame_size=(640, 480))
    progress = tracker.progress

    assert tracker.update(far, 2.4, frame_size=(640, 480)) is False
    assert tracker.progress == pytest.approx(progress)

    assert tracker.update(near, 2.4, frame_size=(640, 480)) is False
    assert tracker.update(near, 2.9, frame_size=(640, 480)) is True


def test_release_gate_needs_the_hand_open_for_a_moment():
    from main.nav import GestureSnapshot, ReleaseGate

    fist = GestureSnapshot(label="Closed_Fist", score=1.0)
    gate = ReleaseGate(required=True, open_s=0.12)
    assert not gate.update(fist, 1.0)
    assert not gate.update(None, 1.05)  # one-frame flicker
    assert not gate.update(fist, 1.1)
    assert not gate.update(None, 1.2)
    assert gate.update(None, 1.35)
    assert gate.update(fist, 1.4)  # stays released
    assert ReleaseGate(required=False).released
