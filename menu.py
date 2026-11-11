#!/usr/bin/env python3
"""Main game menu for Strike a Pose.

Select and play:
  1. Strike a Pose (party game)
  2. Wild West Duel
  3. Dodgeball

Usage:
  python menu.py            # Opens graphical selection menu
  python menu.py --cli      # Opens terminal text menu
  python menu.py pose       # Directly launches Strike a Pose
  python menu.py duel       # Directly launches Wild West Duel
  python menu.py dodgeball  # Directly launches Dodgeball
"""

from __future__ import annotations

import sys
from strike_a_pose.menu import (
    GAMES,
    GAME_KEYS,
    main,
    parse_args,
    run_menu,
    show_cli_menu,
    show_gui_menu,
    show_menu,
    trigger_game,
)

__all__ = [
    "GAMES",
    "GAME_KEYS",
    "main",
    "parse_args",
    "run_menu",
    "show_cli_menu",
    "show_gui_menu",
    "show_menu",
    "trigger_game",
]

if __name__ == "__main__":
    sys.exit(main())
