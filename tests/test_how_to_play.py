"""How-to-play page between the menu and a game's ready-up."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from main import content
from main.games.how_to_play import HowToPlayGame, guide_for
from main.games.registry import build_registry, make_how_to
from main.nav import GestureSnapshot, MenuCommand, StartGame
from main.pose import PoseFrame

from cursor_util import hand_for


def _frame(timestamp: float) -> PoseFrame:
    return PoseFrame(np.zeros((480, 640, 3), np.uint8), timestamp, (None, None), [])


def _snap(label, x=10.0, y=10.0) -> GestureSnapshot:
    pts = tuple([(x, y)] * 21)
    return GestureSnapshot(label=label, score=1.0 if label else 0.0, landmarks=pts)


def test_guides_cover_every_registered_game_and_fill_in_settings():
    registry = build_registry()
    for game_id, entry in registry.items():
        assert game_id in content.HowToPlay.guides
        guide = guide_for(game_id, entry.facts)
        assert len(guide.steps) == 3
        assert "{" not in "".join(h + s for h, s in guide.steps) + "".join(guide.fact)
    assert guide_for("duel", {"lives": 3}).fact[0] == "3 lives each"


def _show(page: HowToPlayGame, label, x, y, t: float) -> None:
    page.gesture_snapshot = _snap(label, x, y)
    page.update(_frame(t))


def _aim(page: HowToPlayGame, target, t: float, label=None):
    """Move the hand so the cursor sits on `target`; held ~0.2s. Returns (hand, t)."""
    hand = hand_for(*target)
    for _ in range(6):
        t += 1 / 30
        _show(page, label, *hand, t)
    return hand, t


def test_cursor_uses_the_menu_mapping_so_it_does_not_jump_between_pages():
    from main.games.menu import MenuGame
    from main.games.registry import GameEntry

    pygame.init()
    menu = MenuGame((640, 480), (GameEntry("duel", "Duel", lambda size: None),))
    page = HowToPlayGame((640, 480), "duel")
    assert page.cursor is None  # no hand yet: nothing drawn, nothing parked at the centre
    snap = _snap(None, 500.0, 120.0)
    menu.gesture_snapshot = page.gesture_snapshot = snap
    menu.update(_frame(1.0))
    page.update(_frame(1.0))
    assert page.cursor == menu.cursor.position


def test_fist_away_from_buttons_does_nothing():
    pygame.init()
    page = HowToPlayGame((640, 480), "duel", release_first=False)
    _show(page, None, 320.0, 240.0, 1.0)
    _show(page, "Closed_Fist", 320.0, 240.0, 1.1)
    _show(page, "Closed_Fist", 320.0, 240.0, 2.0)
    assert page.poll_nav() is None


def test_fist_carried_from_menu_cannot_select_even_over_a_button():
    pygame.init()
    page = HowToPlayGame((640, 480), "duel")
    play = page.button_rects()[0].center
    hand, t = _aim(page, play, 1.0, label="Closed_Fist")  # still closed from the menu pick
    assert page.button_rects()[0].collidepoint(page.cursor)
    assert page.debug_lines()[0].endswith("play")  # selected, but the carried fist can't press
    _show(page, "Closed_Fist", *hand, t + 1.0)
    assert page.poll_nav() is None

    _show(page, None, *hand, t + 1.1)  # opens…
    _show(page, None, *hand, t + 1.3)
    _show(page, "Closed_Fist", *hand, t + 1.4)  # …and closes again on Let's go!
    _show(page, "Closed_Fist", *hand, t + 2.0)
    assert page.poll_nav() == StartGame("duel")


def test_hover_lets_go_then_fist_starts_the_game():
    pygame.init()
    page = HowToPlayGame((640, 480), "dodgeball")
    hand, t = _aim(page, page.button_rects()[0].center, 1.0)
    assert page.debug_lines()[0].endswith("play")
    _show(page, "Closed_Fist", *hand, t + 0.1)
    _show(page, "Closed_Fist", *hand, t + 0.7)
    assert page.poll_nav() == StartGame("dodgeball")


def test_selection_sticks_so_a_fist_away_from_the_button_presses_it():
    pygame.init()
    page = HowToPlayGame((640, 480), "duel")
    hand, t = _aim(page, page.button_rects()[0].center, 1.0)
    away = (hand[0], hand[1] + 150.0)  # cursor drifts well off Let's go!
    for k in range(10):
        _show(page, None, *away, t + 0.05 * (k + 1))
    t += 0.5
    assert not page.button_rects()[0].collidepoint(page.cursor)
    _show(page, "Closed_Fist", *away, t + 0.1)
    _show(page, "Closed_Fist", *away, t + 0.7)
    assert page.poll_nav() == StartGame("duel")


def test_hover_back_then_fist_returns_to_menu():
    pygame.init()
    page = HowToPlayGame((640, 480), "strike")
    hand, t = _aim(page, page.button_rects()[1].center, 1.0)
    _show(page, "Closed_Fist", *hand, t + 0.1)
    _show(page, "Closed_Fist", *hand, t + 0.7)
    assert page.poll_nav() == StartGame(None)


def test_keyboard_enter_plays_and_back_command_leaves():
    pygame.init()
    page = HowToPlayGame((640, 480), "duel")
    page.handle_command(MenuCommand.SELECT)
    assert page.poll_nav() == StartGame("duel")
    page.handle_command(MenuCommand.MOVE_DOWN)
    page.handle_command(MenuCommand.SELECT)
    assert page.poll_nav() == StartGame(None)
    page.handle_command(MenuCommand.BACK)
    assert page.poll_nav() == StartGame(None)


def test_how_to_factory_builds_pages_and_skips_unknown_ids():
    factory = make_how_to(build_registry())
    page = factory((640, 480), "strike")
    assert isinstance(page, HowToPlayGame)
    assert page.owns_gestures and page.wants_gestures
    assert factory((640, 480), "nope") is None


def test_draw_smoke_every_guide():
    pygame.init()
    canvas = pygame.Surface((640, 480))
    for game_id in content.HowToPlay.guides:
        page = HowToPlayGame((640, 480), game_id)
        page.gesture_snapshot = _snap("Closed_Fist", 320, 240)
        page.draw(canvas, _frame(1.0))
