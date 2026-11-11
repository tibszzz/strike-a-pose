"""Shell navigation and menu command seam.

Keys (and later camera gestures) map to `MenuCommand`. Games that care
implement `handle_command`. `poll_nav` lets a game ask the shell to swap
titles or quit without owning the window or pose tracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class MenuCommand(Enum):
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    SELECT = auto()
    BACK = auto()


@dataclass(frozen=True)
class StartGame:
    game_id: str


@dataclass(frozen=True)
class QuitApp:
    pass


Nav = StartGame | QuitApp
