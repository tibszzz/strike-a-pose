"""Splash/menu primary-hand skeleton + hold ring (pygame)."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.games.menu import MenuGame
from main.games.registry import GameEntry
from main.games.splash import SplashGame
from main.games.strike.play import StrikeGame
from main.nav import GestureSnapshot, HandGesture, NAV_GESTURE_HANDS
from main.nav.hand_draw import draw_primary_hand_hold
from main.pose import PoseFrame


def _entries() -> tuple[GameEntry, ...]:
    return (GameEntry("strike", "Strike a Pose", lambda size: None),)


def _frame(size=(480, 640), timestamp: float = 1.0) -> PoseFrame:
    h, w = size
    return PoseFrame(np.zeros((h, w, 3), np.uint8), timestamp, (None, None), [])


def test_splash_menu_strike_share_one_gesture_hand():
    assert SplashGame.gesture_hands == NAV_GESTURE_HANDS
    assert MenuGame.gesture_hands == NAV_GESTURE_HANDS
    # Strike uses many hands in ready-up; mid-game / results use one (end screen).
    game = StrikeGame((640, 480))
    game._in_ready_up = False
    assert game.gesture_hands == NAV_GESTURE_HANDS


def test_draw_primary_hand_hold_skeleton_always_ring_when_holding(monkeypatch):
    pygame.init()
    surface = pygame.Surface((200, 200))
    drawn_skel: list[tuple] = []
    drawn_ring: list[tuple] = []

    def fake_skel(surf, landmarks, color):
        drawn_skel.append((tuple(landmarks), color))

    def fake_ring(surf, center, radius, progress, *, track_color, fill_color):
        drawn_ring.append((center, radius, progress))

    monkeypatch.setattr("main.nav.hand_draw.draw_hand_skeleton", fake_skel)
    monkeypatch.setattr("main.nav.hand_draw.draw_hold_ring", fake_ring)

    primary = tuple((float(i), float(i)) for i in range(21))
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.9,
        landmarks=primary,
        hand_box=(0.0, 0.0, 30.0, 40.0),
        hands=(HandGesture("Thumb_Up", 0.9, (0.0, 0.0, 30.0, 40.0), primary),),
    )
    draw_primary_hand_hold(surface, snap, 0.0, color=(255, 220, 80))
    assert len(drawn_skel) == 1
    assert drawn_skel[0][0] == primary
    assert len(drawn_ring) == 1
    assert drawn_ring[0][2] == 0.0

    drawn_skel.clear()
    drawn_ring.clear()
    idle = GestureSnapshot(label="Victory", score=0.9, landmarks=primary)
    draw_primary_hand_hold(surface, idle, 0.0, color=(255, 220, 80))
    assert len(drawn_skel) == 1
    assert drawn_ring == []


def test_splash_draw_uses_primary_hand_hold(monkeypatch):
    pygame.init()
    calls: list[tuple] = []

    def fake_draw(surf, snap, progress, *, color):
        calls.append((snap, progress, color))

    monkeypatch.setattr("main.games.splash.draw_primary_hand_hold", fake_draw)
    splash = SplashGame((640, 480))
    primary = tuple((10.0 + i, 20.0) for i in range(21))
    splash.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=primary,
        hand_box=(0.0, 0.0, 40.0, 40.0),
    )
    splash._thumb._progress = 0.4
    splash.draw(pygame.Surface((640, 480)), _frame())
    assert len(calls) == 1
    assert calls[0][0] is splash.gesture_snapshot
    assert calls[0][1] == 0.4


def test_menu_draw_passes_hold_progress_to_paper_cursor(monkeypatch):
    pygame.init()
    calls: list[tuple] = []

    def fake_draw(surf, frame, snap, progress, *, at):
        calls.append((snap, progress))

    monkeypatch.setattr("main.ui.widgets.draw_cursor", fake_draw)
    menu = MenuGame((640, 480), _entries())
    menu._hard_lock = 0
    primary = tuple((100.0 + i, 200.0) for i in range(21))
    menu.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=primary,
        hand_box=(80.0, 180.0, 140.0, 240.0),
    )
    menu._thumb._progress = 0.5
    menu.draw(pygame.Surface((640, 480)), _frame())
    assert len(calls) == 1
    assert calls[0][1] == 0.5
