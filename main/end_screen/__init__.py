"""Shared match-end results page with a Play again / Menu chooser."""

from .draw import (
    LivesRow,
    TableRow,
    draw_card_art,
    draw_end_screen,
    draw_headline,
    draw_lives_rows,
    draw_points_table,
    winners_line,
)
from .logic import EndChoice, EndScreen, EndScreenConfig

__all__ = [
    "EndChoice",
    "EndScreen",
    "EndScreenConfig",
    "LivesRow",
    "TableRow",
    "draw_card_art",
    "draw_end_screen",
    "draw_headline",
    "draw_lives_rows",
    "draw_points_table",
    "winners_line",
]
