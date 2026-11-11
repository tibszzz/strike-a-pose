"""Registry, menu navigation, and COCO→library person conversion."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main.games.menu import MenuGame
from main.games.registry import GameEntry, build_registry
from main.games.splash import SplashGame
from main.nav import MenuCommand, QuitApp, StartGame
from main.pose import PoseFrame, assign_players
from main.pose.library import JOINT_NAMES, from_coco_person

from test_gestures import person


def test_build_registry_lists_playable_games():
    registry = build_registry()
    assert list(registry) == ["duel", "dodgeball", "cannonball", "strike"]
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


def test_menu_select_emits_start_game():
    pygame.init()
    entries = (
        GameEntry("duel", "Wild West Duel", lambda size: None),
        GameEntry("strike", "Strike a Pose", lambda size: None),
    )
    menu = MenuGame((640, 480), entries)
    menu.handle_command(MenuCommand.MOVE_DOWN)
    menu.handle_command(MenuCommand.SELECT)
    assert menu.poll_nav() == StartGame("strike")
    assert menu.poll_nav() is None


def test_menu_back_emits_quit_app():
    pygame.init()
    entries = (GameEntry("duel", "Wild West Duel", lambda size: None),)
    menu = MenuGame((640, 480), entries)
    menu.handle_command(MenuCommand.BACK)
    assert menu.poll_nav() == QuitApp()


def test_menu_wants_gestures_and_passthrough_camera():
    pygame.init()
    entries = (GameEntry("duel", "Wild West Duel", lambda size: None),)
    menu = MenuGame((640, 480), entries)
    assert menu.wants_gestures is True
    image = np.zeros((480, 640, 3), np.uint8)
    assert menu.render_camera(image) is image


def test_splash_thumbs_up_opens_menu():
    pygame.init()
    splash = SplashGame((640, 480))
    assert splash.wants_gestures is True
    assert splash.is_splash is True
    splash.handle_command(MenuCommand.MOVE_UP)
    assert splash.poll_nav() == StartGame(None)
    assert splash.poll_nav() is None


def test_splash_enter_opens_menu_and_back_quits():
    pygame.init()
    splash = SplashGame((640, 480))
    splash.handle_command(MenuCommand.SELECT)
    assert splash.poll_nav() == StartGame(None)
    splash.handle_command(MenuCommand.BACK)
    assert splash.poll_nav() == QuitApp()
    image = np.zeros((480, 640, 3), np.uint8)
    assert splash.render_camera(image) is image
