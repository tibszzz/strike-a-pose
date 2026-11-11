"""Menu commands and shell navigation events."""

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
