"""Marker stick-figure backdrop behind the menu, how-to-play and results pages."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.pose import PoseFrame
from main.pose.types import Person
from main.ui import sketch

W, H = 320, 240


def _person(cx: float, conf: float = 0.9) -> Person:
    offsets = [
        (0, 30), (-3, 26), (3, 26), (-7, 28), (7, 28),  # face
        (-16, 50), (16, 50), (-24, 80), (24, 80), (-28, 110), (28, 110),  # arms
        (-10, 120), (10, 120), (-12, 160), (12, 160), (-14, 200), (14, 200),  # legs
    ]
    xy = np.array([(cx + dx, dy) for dx, dy in offsets], np.float32)
    return Person(xy, np.full(17, conf, np.float32), (cx - 30, 20, cx + 30, 205))


def _frame(people, size=(W, H)) -> PoseFrame:
    w, h = size
    return PoseFrame(np.zeros((h, w, 3), np.uint8), 1.0, (None, None), list(people))


def _render(pose) -> np.ndarray:
    sketch.reset_smoothing()
    surface = pygame.Surface((W, H))
    sketch.draw_sketch_backdrop(surface, pose)
    return pygame.surfarray.array3d(surface)


def test_no_people_is_plain_paper():
    assert np.array_equal(_render(None), _render(_frame([])))


def test_person_is_sketched_where_they_stand():
    blank = _render(_frame([]))
    drawn = _render(_frame([_person(80)]))
    changed = np.any(drawn != blank, axis=2)  # (W, H)
    xs = np.nonzero(changed.any(axis=1))[0]
    assert changed.any()
    assert xs.min() >= 30 and xs.max() <= 130  # stays around the person, not elsewhere


def test_low_confidence_people_are_skipped():
    assert np.array_equal(_render(_frame([])), _render(_frame([_person(80, conf=0.1)])))


def test_keypoints_scale_from_camera_to_canvas():
    # Same person on a 2x camera image lands at half the coordinates on the canvas.
    big = _person(80)
    big = Person(big.xy * 2, big.conf, big.box)
    a = _render(_frame([_person(80)]))
    b = _render(_frame([big], size=(W * 2, H * 2)))
    blank = _render(_frame([]))
    ca = np.any(a != blank, axis=2)
    cb = np.any(b != blank, axis=2)
    assert abs(np.nonzero(ca.any(axis=1))[0].mean() - np.nonzero(cb.any(axis=1))[0].mean()) < 10


def test_menu_and_how_to_draw_sketch_backdrop(monkeypatch):
    from main.games.registry import build_registry, make_how_to, make_menu

    calls = []
    monkeypatch.setattr(sketch, "draw_sketch_backdrop", lambda s, pose=None: calls.append(pose))
    pose = _frame([_person(80)])
    reg = build_registry()
    menu = make_menu(reg)((W, H))
    assert not hasattr(menu, "render_camera")  # no live video behind the menu
    menu.draw(pygame.Surface((W, H)), pose)
    make_how_to(reg)((W, H), "strike").draw(pygame.Surface((W, H)), pose)
    assert calls == [pose, pose]


def test_keypoint_jitter_is_smoothed_between_frames():
    sketch.reset_smoothing()
    surface = pygame.Surface((W, H))
    sketch.draw_sketch_backdrop(surface, _frame([_person(80)]))
    shaken = _person(80)
    shaken = Person(shaken.xy + (6.0, 0.0), shaken.conf, shaken.box)
    pose = PoseFrame(np.zeros((H, W, 3), np.uint8), 1.0 + 1 / 30, (None, None), [shaken])
    out = sketch._smoother.update([(shaken.xy, shaken.conf)], pose.timestamp)
    dx = float(out[0][0][0, 0] - _person(80).xy[0, 0])
    assert 0 < dx < 6  # moved toward the new spot, but not all the way


def test_faded_hint_bar_is_paper_not_black():
    from main.ui import paper, widgets
    from main.ui.paper import Frame
    from main.ui.widgets import Hint

    surface = pygame.Surface((640, 480))
    surface.fill((255, 255, 255))
    frame = Frame(640, 480)
    rect = frame.rect(50, 770, 610, 846)
    hints = (Hint(widgets.PALM_ICON, "Open palm", "Move"), Hint(widgets.FIST_ICON, "Fist", "Close"))
    widgets.draw_hint_bar(surface, frame, rect, hints, scale=0.68, alpha=150)
    px = pygame.surfarray.array3d(surface)[rect.x + 4 : rect.right - 4, rect.y + 8 : rect.bottom - 8]
    assert (px.sum(axis=2) < 150).mean() < 0.02  # almost no near-black pixels
    assert abs(px.reshape(-1, 3).mean(axis=0) - np.array(paper.PAPER)).max() < 30
