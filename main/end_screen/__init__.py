"""Shared match-end Replay / Menu chooser."""

from .draw import draw_end_screen
from .logic import EndChoice, EndScreen, EndScreenConfig

__all__ = [
    "EndChoice",
    "EndScreen",
    "EndScreenConfig",
    "draw_end_screen",
]
