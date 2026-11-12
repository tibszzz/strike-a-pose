"""Shared hand geometry for nav + strike hold chrome."""

from __future__ import annotations

from main.nav.hand_geometry import (
    NAV_GESTURE_HANDS,
    hand_ring_radius,
    palm_center,
    show_hold_ring,
)


def test_nav_tracks_one_gesture_hand():
    assert NAV_GESTURE_HANDS == 1


def test_palm_center_averages_wrist_and_mcps():
    # Indices 0,5,9,13,17 → (0,0), (10,0), (20,0), (30,0), (40,0) → mean x=20
    landmarks = [(float(i), 0.0) for i in range(21)]
    landmarks[0] = (0.0, 0.0)
    landmarks[5] = (10.0, 0.0)
    landmarks[9] = (20.0, 0.0)
    landmarks[13] = (30.0, 0.0)
    landmarks[17] = (40.0, 0.0)
    assert palm_center(landmarks) == (20.0, 0.0)


def test_palm_center_empty_is_none():
    assert palm_center(()) is None


def test_hand_ring_radius_is_half_box_diagonal():
    # 30×40 box → diagonal 50 → radius 25
    assert hand_ring_radius((0.0, 0.0, 30.0, 40.0)) == 25.0


def test_show_hold_ring_when_progress_or_thumb_up():
    assert show_hold_ring(0.0, None) is False
    assert show_hold_ring(0.0, "Victory") is False
    assert show_hold_ring(0.1, "Victory") is True
    assert show_hold_ring(0.0, "Thumb_Up") is True
