"""Smoothed hand cursor shared by the menu, how-to-play and results pages."""

from main.nav import GestureSnapshot
from main.nav.cursor import HandCursor, OneEuro


def _snap(x: float, y: float, label=None) -> GestureSnapshot:
    return GestureSnapshot(label=label, score=1.0 if label else 0.0, landmarks=tuple([(x, y)] * 21))


def _fist_snap(palm: tuple[float, float], tip: tuple[float, float]) -> GestureSnapshot:
    pts = [palm] * 21
    pts[8] = tip  # index fingertip curls down when the hand closes
    return GestureSnapshot(label="Closed_Fist", score=1.0, landmarks=tuple(pts))


def test_follows_the_palm_not_the_fingertip():
    cur = HandCursor((640, 480), smooth=False)
    cur.update(_snap(300, 200), 1.0)
    assert cur.update(_fist_snap((300, 200), (300, 260)), 1.1) == (300, 200)


def test_absolute_gain_maps_around_the_centre_and_clamps():
    cur = HandCursor((640, 480), gain=2.0, smooth=False)
    assert cur.update(_snap(420, 240), 1.0) == (520, 240)
    assert cur.update(_snap(640, 0), 1.1) == (639, 0)
    assert cur.hand_point_for((520, 240)) == (420, 240)


def test_absolute_cursor_survives_short_dropouts_then_hides():
    cur = HandCursor((640, 480), grace_s=0.3, smooth=False)
    cur.update(_snap(100, 100), 1.0)
    assert cur.update(None, 1.2) == (100, 100) and not cur.tracking
    assert cur.update(None, 1.4) is None


def test_relative_starts_centred_and_moves_by_hand_motion_times_gain():
    cur = HandCursor((640, 480), relative=True, gain=2.0, smooth=False)
    assert cur.position == (320, 240)
    cur.update(_snap(600, 50), 1.0)  # first sighting only anchors
    assert cur.position == (320, 240)
    cur.update(_snap(590, 60), 1.1)
    assert cur.position == (300, 260)


def test_relative_short_dropout_keeps_the_anchor_long_one_reanchors():
    cur = HandCursor((640, 480), relative=True, grace_s=0.3, smooth=False)
    cur.update(_snap(100, 100), 1.0)
    cur.update(None, 1.1)
    cur.update(_snap(120, 100), 1.2)  # back within grace: the motion during the gap counts
    assert cur.position == (340, 240)
    cur.update(None, 1.3)
    cur.update(None, 1.7)
    cur.update(_snap(500, 400), 1.8)  # gone too long: re-anchor, no jump
    assert cur.position == (340, 240)


def test_relative_edge_clamp_drags_the_anchor():
    cur = HandCursor((640, 480), relative=True, smooth=False)
    cur.update(_snap(300, 240), 1.0)
    cur.update(_snap(300, -400), 1.1)
    assert cur.position[1] == 0.0
    cur.update(_snap(300, -380), 1.2)  # straight back down responds immediately
    assert cur.position[1] == 20.0


def test_one_euro_damps_jitter_but_tracks_big_moves():
    f = OneEuro(min_cutoff=1.0, beta=0.02)
    f((100.0, 100.0), 0.0)
    t, jitter = 0.0, []
    for k in range(30):
        t += 1 / 30
        jitter.append(f((100.0 + (3 if k % 2 else -3), 100.0), t)[0])
    assert max(jitter) - min(jitter) < 3  # ±3 px noise → well under 6 px of wobble
    for _ in range(10):
        t += 1 / 30
        x, _ = f((400.0, 100.0), t)
    assert x > 380  # a fast 300 px move arrives within ~1/3 s


# --- body-scaled reach ----------------------------------------------------------------

import numpy as np
import pytest

from main.nav.cursor import Reach, body_frame, hand_owner
from main.pose.types import Person


def _body(cx: float, shoulder_y: float, torso: float, wrist=None, hips=True) -> Person:
    """Person with shoulders at (cx ± torso/3, shoulder_y), hips one torso lower."""
    xy = np.zeros((17, 2), np.float32)
    conf = np.zeros(17, np.float32)
    half = torso / 3
    xy[5], xy[6] = (cx - half, shoulder_y), (cx + half, shoulder_y)
    conf[5] = conf[6] = 0.9
    if hips:
        xy[11], xy[12] = (cx - half * 0.7, shoulder_y + torso), (cx + half * 0.7, shoulder_y + torso)
        conf[11] = conf[12] = 0.9
    if wrist is not None:
        xy[10], conf[10] = wrist, 0.9
    return Person(xy, conf, (cx - torso, shoulder_y - torso, cx + torso, shoulder_y + 2 * torso))


REACH = Reach(half_w=1.0, top=1.0, bottom=0.5)


def _reach_cursor(**kw) -> HandCursor:
    return HandCursor((640, 480), smooth=False, reach=REACH, **kw)


def test_body_frame_uses_torso_or_shoulder_width_when_hips_are_hidden():
    assert body_frame(_body(300, 200, 120)) == ((300, 200), 120)
    (_, torso) = body_frame(_body(300, 200, 120, hips=False))
    assert torso == 1.3 * 80  # 1.3 × shoulder width (2 × torso/3)


def test_hand_is_matched_to_the_person_whose_wrist_it_is_on():
    a = _body(150, 200, 100, wrist=(160, 120))
    b = _body(480, 200, 100, wrist=(470, 120))
    assert hand_owner([a, b], (472, 118))[0] == pytest.approx((480, 200))
    assert hand_owner([a, b], (320, 400)) is None  # nobody's wrist near


def test_absolute_reach_is_the_same_near_and_far():
    # Hand one torso up and one torso right of the shoulders → top-right corner,
    # whether the player is small (far) or big (close) in the frame.
    far, near = _reach_cursor(), _reach_cursor()
    small = _body(200, 300, 60, wrist=(260, 240))
    big = _body(320, 300, 200, wrist=(520, 100))
    assert far.update(_snap(260, 240), 1.0, [small]) == pytest.approx((639, 0), abs=1e-6)
    assert near.update(_snap(520, 100), 1.0, [big]) == pytest.approx((639, 0), abs=1e-6)
    # Hand on the shoulder midpoint → horizontally centred, 1/1.5 of the way down.
    assert far.update(_snap(200, 300), 1.1, [_body(200, 300, 60, wrist=(200, 300))]) == pytest.approx((320, 320), abs=1e-6)


def test_relative_gain_scales_inversely_with_body_size():
    small, big = _reach_cursor(relative=True), _reach_cursor(relative=True)
    s, b = _body(320, 300, 60, wrist=(320, 250)), _body(320, 300, 180, wrist=(320, 250))
    small.update(_snap(320, 250), 1.0, [s])
    big.update(_snap(320, 250), 1.0, [b])
    small.update(_snap(330, 250), 1.1, [s])
    big.update(_snap(330, 250), 1.1, [b])
    moved_small = small.position[0] - 320
    moved_big = big.position[0] - 320
    assert moved_small == pytest.approx(3 * moved_big)  # a third the size → three times the reach


def test_falls_back_to_fixed_gain_without_a_body():
    cur = _reach_cursor(gain=2.0)
    assert cur.update(_snap(420, 240), 1.0, []) == (520, 240)
