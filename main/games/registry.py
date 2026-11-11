"""Playable games the shell and menu can start.

`SplashGame` / `MenuGame` are bootstrap-only and are not listed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Size = tuple[int, int]
GameFactory = Callable[[Size], Any]


@dataclass(frozen=True)
class GameEntry:
    id: str
    label: str
    factory: GameFactory


def _duel(size: Size):
    from main.games.duel.game import DuelGame

    return DuelGame(size)


def _dodgeball(size: Size):
    from main.games.dodgeball.dodgeball import DodgeballGame

    return DodgeballGame(size)


def _cannonball(size: Size):
    from main.games.dodgeball.cannonball import CannonballGame

    return CannonballGame(size)


def build_registry(*, strike_config=None) -> dict[str, GameEntry]:
    """Factories for every title shown in the menu and accepted on the CLI."""
    from main.config import Config
    from main.games.strike.play import StrikeGame

    config = strike_config if strike_config is not None else Config()

    def strike(size: Size):
        return StrikeGame(size, config=config)

    return {
        "duel": GameEntry("duel", "Wild West Duel", _duel),
        "dodgeball": GameEntry("dodgeball", "Dodgeball", _dodgeball),
        "cannonball": GameEntry("cannonball", "Cannonball", _cannonball),
        "strike": GameEntry("strike", "Strike a Pose", strike),
    }


def make_menu(registry: dict[str, GameEntry]) -> GameFactory:
    from main.games.menu import MenuGame

    entries = tuple(registry[key] for key in registry)

    def factory(size: Size):
        return MenuGame(size, entries)

    return factory


def make_splash() -> GameFactory:
    from main.games.splash import SplashGame

    def factory(size: Size):
        return SplashGame(size)

    return factory
