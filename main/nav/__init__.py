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
    HandGesture,
    load_gesture_nav_config,
)
from .cursor import HandCursor, nav_cursor
from .hand_geometry import NAV_GESTURE_HANDS
from .thumb_hold import ReleaseGate, ThumbHoldTracker, effective_label, hand_anchor
from .types import MenuCommand, Nav, QuitApp, StartGame

__all__ = [
    "GestureCommandMapper",
    "GestureNavConfig",
    "GestureRecognizerSession",
    "GestureSnapshot",
    "HandCursor",
    "HandGesture",
    "LABEL_TO_COMMAND",
    "MenuCommand",
    "NAV_GESTURE_HANDS",
    "Nav",
    "QuitApp",
    "ReleaseGate",
    "StartGame",
    "ThumbHoldTracker",
    "effective_label",
    "hand_anchor",
    "load_gesture_nav_config",
    "nav_cursor",
]
