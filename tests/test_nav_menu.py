"""Registry, menu navigation, and COCO→library person conversion."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from main.games.menu import INDEX_FINGERTIP, MenuGame
from main.games.registry import GameEntry, build_registry
from main.games.splash import SplashGame
from main.nav import GestureSnapshot, MenuCommand, QuitApp, StartGame
from main.pose import PoseFrame, assign_players
from main.pose.library import JOINT_NAMES, from_coco_person

from test_gestures import person


def _frame(size=(480, 640), timestamp: float = 1.0) -> PoseFrame:
    h, w = size
    return PoseFrame(np.zeros((h, w, 3), np.uint8), timestamp, (None, None), [])


def _landmarks_at(
    x: float,
    y: float,
    count: int = 21,
    wrist: tuple[float, float] | None = None,
) -> tuple[tuple[float, float], ...]:
    pts = [(0.0, 0.0)] * count
    pts[0] = wrist if wrist is not None else (x, y)
    pts[INDEX_FINGERTIP] = (x, y)
    return tuple(pts)


def _entries() -> tuple[GameEntry, GameEntry, GameEntry]:
    return (
        GameEntry("duel", "Wild West Duel", lambda size: None),
        GameEntry("dodgeball", "Dodgeball", lambda size: None),
        GameEntry("strike", "Strike a Pose", lambda size: None),
    )


def test_build_registry_lists_playable_games():
    registry = build_registry()
    assert list(registry) == ["duel", "dodgeball", "strike"]
    assert "cannonball" not in registry
    assert "menu" not in registry


def test_from_coco_person_maps_named_joints():
    coco = person()
    named = from_coco_person(coco)
    assert set(named.joints) == set(JOINT_NAMES)
    assert named.joints["nose"] == (float(coco.xy[0][0]), float(coco.xy[0][1]))
    assert named.box == tuple(map(float, coco.box))


def test_pose_frame_keeps_people_and_players():
    left = person(box=(40, 80, 200, 540))
    right = person(box=(440, 80, 600, 540))
    people = [left, right]
    frame = PoseFrame(
        np.zeros((480, 640, 3), np.uint8),
        1.0,
        assign_players(people, 640),
        people,
    )
    assert frame.people == people
    assert frame.players[0] is left
    assert frame.players[1] is right


def test_menu_keyboard_lock_and_select():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    menu.handle_command(MenuCommand.MOVE_DOWN)
    menu.handle_command(MenuCommand.MOVE_DOWN)
    menu.handle_command(MenuCommand.SELECT)
    assert menu.poll_nav() == StartGame("dodgeball")
    assert menu.poll_nav() is None


def test_menu_select_without_lock_is_noop():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    menu.handle_command(MenuCommand.SELECT)
    assert menu.poll_nav() is None


def test_menu_back_emits_quit_app():
    pygame.init()
    menu = MenuGame((640, 480), _entries()[:1])
    menu.handle_command(MenuCommand.BACK)
    assert menu.poll_nav() == QuitApp()


def test_menu_wants_gestures_and_passthrough_camera():
    pygame.init()
    menu = MenuGame((640, 480), _entries()[:1])
    assert menu.wants_gestures is True
    image = np.zeros((480, 640, 3), np.uint8)
    assert menu.render_camera(image) is image


def test_menu_pointing_up_updates_lock_while_moving():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    r0, r1 = menu.tile_rects()[0], menu.tile_rects()[1]
    tip0, tip1 = (r0.centerx, r0.centery), (r1.centerx, r1.centery)

    menu.gesture_snapshot = GestureSnapshot(
        label="Pointing_Up", score=1.0, landmarks=_landmarks_at(*tip0)
    )
    menu.update(_frame(timestamp=1.0))
    assert menu.debug_lines()[0] == "menu lock duel"

    # Still holding Pointing_Up while tip moves — selection follows the tip.
    menu.gesture_snapshot = GestureSnapshot(
        label="Pointing_Up", score=1.0, landmarks=_landmarks_at(*tip1)
    )
    menu.update(_frame(timestamp=1.1))
    assert menu.debug_lines()[0] == "menu lock dodgeball"


def test_menu_pointing_up_locks_and_held_thumbs_up_starts():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    rect = menu.tile_rects()[1]
    tip = (rect.centerx, rect.centery)
    menu.gesture_snapshot = GestureSnapshot(
        label="Pointing_Up",
        score=1.0,
        landmarks=_landmarks_at(*tip),
    )
    menu.update(_frame(timestamp=1.0))
    menu.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up",
        score=1.0,
        landmarks=_landmarks_at(*tip),
    )
    menu.update(_frame(timestamp=1.0))  # hold starts
    menu.update(_frame(timestamp=1.9))  # 0.9s — not enough
    assert menu.poll_nav() is None
    menu.update(_frame(timestamp=2.0))  # 1.0s — confirm
    assert menu.poll_nav() == StartGame("dodgeball")


def test_menu_thumbs_up_without_hard_lock_is_noop():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    rect = menu.tile_rects()[0]
    tip = (rect.centerx, rect.centery)
    menu.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up",
        score=1.0,
        landmarks=_landmarks_at(*tip),
    )
    menu.update(_frame(timestamp=1.0))
    menu.update(_frame(timestamp=3.0))
    assert menu.poll_nav() is None


def test_menu_thumbs_up_hold_resets_if_released_early():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    menu.handle_command(MenuCommand.MOVE_DOWN)
    tip = menu.tile_rects()[0].center
    menu.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up", score=1.0, landmarks=_landmarks_at(*tip)
    )
    menu.update(_frame(timestamp=1.0))
    menu.update(_frame(timestamp=1.5))  # 0.5s into hold — not enough
    assert menu.poll_nav() is None

    menu.gesture_snapshot = GestureSnapshot(label=None, score=0.0, landmarks=_landmarks_at(*tip))
    menu.update(_frame(timestamp=1.6))

    menu.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up", score=1.0, landmarks=_landmarks_at(*tip)
    )
    menu.update(_frame(timestamp=1.7))
    menu.update(_frame(timestamp=2.6))  # 0.9s — still not enough
    assert menu.poll_nav() is None
    menu.update(_frame(timestamp=2.7))  # 1.0s of continuous hold
    assert menu.poll_nav() == StartGame("duel")


def test_menu_thumbs_up_hold_ignores_other_hand_until_release():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    menu.handle_command(MenuCommand.MOVE_DOWN)
    tip = menu.tile_rects()[0].center
    # Wrist (lm 0) anchors the confirming hand; tip is only for hover.
    near = _landmarks_at(*tip, wrist=(100.0, 200.0))
    far = _landmarks_at(*tip, wrist=(500.0, 200.0))

    menu.gesture_snapshot = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=near)
    menu.update(_frame(timestamp=1.0))
    menu.update(_frame(timestamp=1.5))  # 0.5s in
    assert menu._thumb.progress == pytest.approx(0.5, rel=1e-3)

    # Other hand also Thumb_Up — must not switch or advance the hold clock.
    menu.gesture_snapshot = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=far)
    menu.update(_frame(timestamp=1.9))
    assert menu._thumb.progress == pytest.approx(0.5, rel=1e-3)
    assert menu.poll_nav() is None

    # Original hand still holding — progress resumes from where it left off.
    menu.gesture_snapshot = GestureSnapshot(label="Thumb_Up", score=1.0, landmarks=near)
    menu.update(_frame(timestamp=1.9))
    menu.update(_frame(timestamp=2.4))  # +0.5s → 1.0s total
    assert menu.poll_nav() == StartGame("duel")


def test_menu_reset_clears_hard_lock():
    pygame.init()
    menu = MenuGame((640, 480), _entries())
    menu.handle_command(MenuCommand.MOVE_DOWN)
    menu.reset()
    menu.handle_command(MenuCommand.SELECT)
    assert menu.poll_nav() is None


def test_splash_held_thumbs_up_opens_menu():
    pygame.init()
    splash = SplashGame((640, 480))
    assert splash.wants_gestures is True
    assert splash.is_splash is True
    splash.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),)
    )
    splash.update(_frame(timestamp=1.0))
    splash.update(_frame(timestamp=1.9))  # 0.9s — not enough
    assert splash.poll_nav() is None
    splash.update(_frame(timestamp=2.0))  # 1.0s — open menu
    assert splash.poll_nav() == StartGame(None)
    assert splash.poll_nav() is None


def test_splash_thumbs_up_hold_resets_if_released_early():
    pygame.init()
    splash = SplashGame((640, 480))
    splash.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),)
    )
    splash.update(_frame(timestamp=1.0))
    splash.update(_frame(timestamp=1.5))
    assert splash.poll_nav() is None

    splash.gesture_snapshot = GestureSnapshot(label=None, score=0.0)
    splash.update(_frame(timestamp=1.6))

    splash.gesture_snapshot = GestureSnapshot(
        label="Thumb_Up", score=1.0, landmarks=((100.0, 200.0),)
    )
    splash.update(_frame(timestamp=1.7))
    splash.update(_frame(timestamp=2.6))
    assert splash.poll_nav() is None
    splash.update(_frame(timestamp=2.7))
    assert splash.poll_nav() == StartGame(None)


def test_splash_enter_opens_menu_and_back_quits():
    pygame.init()
    splash = SplashGame((640, 480))
    splash.handle_command(MenuCommand.SELECT)
    assert splash.poll_nav() == StartGame(None)
    splash.handle_command(MenuCommand.BACK)
    assert splash.poll_nav() == QuitApp()
    image = np.zeros((480, 640, 3), np.uint8)
    assert splash.render_camera(image) is image
