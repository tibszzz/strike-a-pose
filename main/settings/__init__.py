"""Adjustable knobs: shared shell settings plus one file per game."""

from __future__ import annotations

from .dodgeball import DodgeballConfig
from .duel import DuelConfig, GestureConfig, ViewConfig
from .env import Messages, env, from_env
from .paths import ASSETS, ROOT
from .shell import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GestureNavConfig,
    load_gesture_nav_config,
)
from .strike import StrikeConfig

# Back-compat alias used across strike call sites and tests.
Config = StrikeConfig

__all__ = [
    "ASSETS",
    "ROOT",
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "Config",
    "DodgeballConfig",
    "DuelConfig",
    "GestureConfig",
    "GestureNavConfig",
    "Messages",
    "StrikeConfig",
    "ViewConfig",
    "env",
    "from_env",
    "load_gesture_nav_config",
]
