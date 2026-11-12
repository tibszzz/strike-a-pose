"""Playable games the shell and menu can start.

`SplashGame` / `MenuGame` are bootstrap-only and are not listed here.
Cannonball remains under `main/games/dodgeball/` but is not registered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from main import content

Size = tuple[int, int]
GameFactory = Callable[[Size], Any]


@dataclass(frozen=True)
class GameEntry:
    id: str
    label: str
    factory: GameFactory
    # Numbers the how-to-play copy quotes ({lives}, {rounds}, …).
    facts: Mapping[str, object] = field(default_factory=dict, compare=False, hash=False)


def build_registry(
    *, strike_config=None, duel_config=None, dodgeball_config=None
) -> dict[str, GameEntry]:
    """Factories for every title shown in the menu and accepted on the CLI."""
    from main.games.dodgeball.dodgeball import DodgeballGame
    from main.games.duel.game import DuelGame
    from main.games.strike.play import StrikeGame
    from main.settings import DodgeballConfig, DuelConfig, StrikeConfig, from_env

    config = strike_config if strike_config is not None else StrikeConfig()
    dodge_cfg = dodgeball_config if dodgeball_config is not None else DodgeballConfig()
    duel_cfg = duel_config if duel_config is not None else from_env(DuelConfig)

    def duel(size: Size):
        return DuelGame(size, config=duel_config)

    def strike(size: Size):
        return StrikeGame(size, config=config)

    def dodgeball(size: Size):
        return DodgeballGame(size, config=dodge_cfg)

    return {
        "duel": GameEntry("duel", content.Registry.duel, duel, {"lives": duel_cfg.lives}),
        "dodgeball": GameEntry(
            "dodgeball",
            content.Registry.dodgeball,
            dodgeball,
            {
                "lives": dodge_cfg.lives,
                "min_players": dodge_cfg.min_players,
                "max_players": dodge_cfg.max_players,
            },
        ),
        "strike": GameEntry(
            "strike",
            content.Registry.strike,
            strike,
            {
                "rounds": config.rounds,
                "min_players": config.min_players,
                "max_players": config.max_players,
            },
        ),
    }


# Menu order (mockup): High Noon, Strike a pose, Dodgeball; unknown ids follow.
MENU_ORDER = ("duel", "strike", "dodgeball")


def make_menu(registry: dict[str, GameEntry]) -> GameFactory:
    from main.games.menu import MenuGame

    ordered = [key for key in MENU_ORDER if key in registry]
    ordered += [key for key in registry if key not in ordered]
    entries = tuple(registry[key] for key in ordered)

    def factory(size: Size):
        # Reached from a fist confirm (results / how-to Back): wait for the hand to open.
        return MenuGame(size, entries, release_first=True)

    return factory


def make_how_to(registry: dict[str, GameEntry]) -> Callable[[Size, str], Any]:
    """How-to-play page factory. Returns None for a title without a guide."""
    from main.games.how_to_play import HowToPlayGame

    def factory(size: Size, game_id: str):
        if game_id not in content.HowToPlay.guides or game_id not in registry:
            return None
        return HowToPlayGame(size, game_id, facts=registry[game_id].facts)

    return factory


def make_splash() -> GameFactory:
    from main.games.splash import SplashGame

    def factory(size: Size):
        return SplashGame(size)

    return factory
