"""Playable games the shell and menu can start.

`SplashGame` / `MenuGame` are bootstrap-only and are not listed here.
Cannonball remains under `main/games/dodgeball/` but is not registered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from main import content

Size = tuple[int, int]
GameFactory = Callable[[Size], Any]


@dataclass(frozen=True)
class GameEntry:
    id: str
    label: str
    factory: GameFactory


def build_registry(
    *, strike_config=None, duel_config=None, dodgeball_config=None
) -> dict[str, GameEntry]:
    """Factories for every title shown in the menu and accepted on the CLI."""
    from main.games.dodgeball.dodgeball import DodgeballGame
    from main.games.duel.game import DuelGame
    from main.games.strike.play import StrikeGame
    from main.settings import DodgeballConfig, StrikeConfig

    config = strike_config if strike_config is not None else StrikeConfig()
    dodge_cfg = dodgeball_config if dodgeball_config is not None else DodgeballConfig()

    def duel(size: Size):
        return DuelGame(size, config=duel_config)

    def strike(size: Size):
        return StrikeGame(size, config=config)

    def dodgeball(size: Size):
        return DodgeballGame(size, config=dodge_cfg)

    return {
        "duel": GameEntry("duel", content.Registry.duel, duel),
        "dodgeball": GameEntry("dodgeball", content.Registry.dodgeball, dodgeball),
        "strike": GameEntry("strike", content.Registry.strike, strike),
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
