"""Draw Replay / Menu tiles over the current game-over frame."""

from __future__ import annotations

import pygame

from main import content, styles
from main.nav import GestureSnapshot
from main.nav.hand_draw import draw_primary_hand_hold
from main.styles import Theme

from .logic import EndChoice, EndScreen

copy = content.EndScreen


def _label(choice: EndChoice) -> str:
    if choice is EndChoice.REPLAY:
        return copy.replay
    return copy.menu


def draw_end_screen(
    canvas: pygame.Surface,
    end: EndScreen,
    *,
    theme: Theme,
    snap: GestureSnapshot | None = None,
    timestamp: float = 0.0,
    dim: bool = True,
) -> None:
    """Overlay two chooser tiles + hint. Does not clear the underlying frame."""
    w, h = end.w, end.h
    if dim:
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill(theme.overlay)
        canvas.blit(overlay, (0, 0))

    tile_font = styles.load_font(theme.font, theme.tile_label_px(h))
    hint_font = styles.load_font(theme.font, theme.hint_px(h))

    for i, (choice, rect) in enumerate(zip(EndScreen.OPTIONS, end.tile_rects())):
        fill = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        fill.fill(theme.tile_fill)
        canvas.blit(fill, rect.topleft)

        locked = i == end.hard_lock
        hovered = i == end.hover
        if locked:
            border_color = theme.accent
            border_w = 5
            name_color = theme.accent
        elif hovered:
            border_color = theme.hover
            border_w = 3
            name_color = theme.ink
        else:
            border_color = theme.muted
            border_w = 2
            name_color = theme.ink

        pygame.draw.rect(canvas, border_color, rect, width=border_w)

        label = tile_font.render(_label(choice), True, name_color)
        # Shrink long labels to fit the tile.
        max_w = max(8, rect.width - 16)
        if label.get_width() > max_w:
            scale = max_w / label.get_width()
            label = pygame.transform.smoothscale(
                label,
                (max(1, int(label.get_width() * scale)), max(1, int(label.get_height() * scale))),
            )
        canvas.blit(
            label,
            (
                rect.centerx - label.get_width() // 2,
                rect.centery - label.get_height() // 2,
            ),
        )

    hint_y = h - hint_font.get_height() - max(16, h // 36)
    hint = hint_font.render(copy.hint, True, theme.ink)
    styles.apply_hint_blink(hint, timestamp)
    canvas.blit(hint, (w // 2 - hint.get_width() // 2, hint_y))

    draw_primary_hand_hold(canvas, snap, end.hold_progress, color=theme.accent)
