"""Shell navigation and menu command seam.

Keys and camera gestures map to `MenuCommand`. Games that care implement
`handle_command`. `poll_nav` lets a game ask the shell to swap titles or
quit without owning the window or pose tracker.
"""

from __future__ import annotations

from .gestures import (
    LABEL_TO_COMMAND,
    GestureCommandMapper,
    GestureNavConfig,
    GestureRecognizerSession,
    GestureSnapshot,
    load_gesture_nav_config,
)
from .thumb_hold import ThumbHoldTracker, effective_label, hand_anchor
from .types import MenuCommand, Nav, QuitApp, StartGame

__all__ = [
    "GestureCommandMapper",
    "GestureNavConfig",
    "GestureRecognizerSession",
    "GestureSnapshot",
    "LABEL_TO_COMMAND",
    "MenuCommand",
    "Nav",
    "QuitApp",
    "StartGame",
    "ThumbHoldTracker",
    "effective_label",
    "hand_anchor",
    "load_gesture_nav_config",
]
