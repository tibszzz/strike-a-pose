"""Unit tests for duel side-camera crop math and track grace."""

import numpy as np

from main.games.duel.preview import (
    PreviewTracker,
    aspect_expand,
    crop_source,
    pad_box,
    smooth_box,
)
from main.pose import Person


def _person(box):
    return Person(xy=np.zeros((17, 2)), conf=np.ones(17), box=box)


def test_pad_box_grows_and_clamps():
    assert pad_box((100, 100, 200, 300), 0.1, 1000, 1000) == (90, 80, 210, 320)
    # clamps at frame edges
    assert pad_box((0, 0, 50, 50), 0.5, 100, 100) == (0, 0, 75, 75)


def test_aspect_expand_matches_target_without_shrinking_body():
    # square 100x100 -> portrait 0.5 (w/h): grow width? 100/100=1 > 0.5 so grow height
    out = aspect_expand((100, 100, 200, 200), 0.5, 1000, 1000)
    x1, y1, x2, y2 = out
    w, h = x2 - x1, y2 - y1
    assert abs(w / h - 0.5) < 1e-6
    # padded body still inside
    assert x1 <= 100 and y1 <= 100 and x2 >= 200 and y2 >= 200


def test_crop_source_pads_then_locks_aspect():
    box = crop_source((100, 50, 180, 250), target_aspect=0.4, pad_frac=0.2, frame_w=1000, frame_h=1000)
    x1, y1, x2, y2 = box
    assert abs((x2 - x1) / (y2 - y1) - 0.4) < 1e-6
    # original box (before pad) contained
    assert x1 < 100 and y1 < 50 and x2 > 180 and y2 > 250


def test_smooth_box_moves_toward_target():
    prev = (0.0, 0.0, 10.0, 10.0)
    target = (10.0, 10.0, 20.0, 20.0)
    mid = smooth_box(prev, target, 0.5)
    assert mid == (5.0, 5.0, 15.0, 15.0)
    assert smooth_box(None, target, 0.5) == target


def test_preview_tracker_grace_then_placeholder():
    t = PreviewTracker(pad=0.0, smooth=1.0, grace=0.3, target_aspect=0.5)
    box = t.update(_person((100, 100, 200, 300)), now=1.0, frame_w=1000, frame_h=1000)
    assert box is not None
    # brief loss still returns last crop
    held = t.update(None, now=1.2, frame_w=1000, frame_h=1000)
    assert held == box
    # after grace -> placeholder
    assert t.update(None, now=1.5, frame_w=1000, frame_h=1000) is None


def test_cover_crop_center_crops_wider_source():
    from main.games.duel.preview import cover_crop

    # 200x100 source into 50x50 dest → keep full height, crop sides to 100x100 in src
    x, y, w, h = cover_crop(200, 100, 50, 50)
    assert (x, y, w, h) == (50.0, 0.0, 100.0, 100.0)


def test_cover_crop_center_crops_taller_source():
    from main.games.duel.preview import cover_crop

    x, y, w, h = cover_crop(100, 200, 50, 50)
    assert (x, y, w, h) == (0.0, 50.0, 100.0, 100.0)


def test_resolve_results_portrait_tracks_then_clears():
    from main.games.duel.preview import resolve_results_portrait

    t = PreviewTracker(pad=0.0, smooth=1.0, grace=0.0, target_aspect=0.5)
    box = resolve_results_portrait(t, _person((100, 100, 200, 300)), now=1.0, frame_w=1000, frame_h=1000)
    assert box is not None
    assert resolve_results_portrait(t, None, now=2.0, frame_w=1000, frame_h=1000) is None
