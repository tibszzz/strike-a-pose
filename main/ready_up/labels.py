"""Above-head player labels with ready checkmarks (no bounding boxes)."""

from __future__ import annotations

from pathlib import Path

import pygame

from main import styles
from main.pose import KP

Rgb = tuple[int, int, int]


def head_anchor(
    box: tuple[float, float, float, float],
    nose: tuple[float, float] | None = None,
    *,
    person_xy=None,
    person_conf=None,
    min_conf: float = 0.3,
) -> tuple[float, float]:
    """Pixel point just above the head for a P-label."""
    if nose is not None:
        return nose[0], nose[1] - 28
    if person_xy is not None and person_conf is not None:
        try:
            if float(person_conf[KP.NOSE]) >= min_conf:
                x, y = float(person_xy[KP.NOSE][0]), float(person_xy[KP.NOSE][1])
                return x, y - 28
        except (IndexError, TypeError, ValueError):
            pass
    x1, y1, x2, _y2 = box
    return (x1 + x2) / 2, y1 - 12


def draw_checkmark(
    canvas: pygame.Surface,
    cx: int,
    cy: int,
    size: int,
    color: Rgb,
    *,
    checked: bool,
) -> None:
    """Small checkbox / check glyph centred on (cx, cy)."""
    s = max(10, size)
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    pad = max(1, s // 10)
    rect = pygame.Rect(pad, pad, s - 2 * pad, s - 2 * pad)
    pygame.draw.rect(surf, (*color, 255), rect, max(1, s // 8), border_radius=max(1, s // 8))
    if checked:
        # Check stroke inside the box
        p1 = (pad + s * 0.18, pad + s * 0.52)
        p2 = (pad + s * 0.40, pad + s * 0.72)
        p3 = (pad + s * 0.78, pad + s * 0.28)
        pygame.draw.lines(surf, (*color, 255), False, [p1, p2, p3], max(2, s // 6))
    canvas.blit(surf, (cx - s // 2, cy - s // 2))


def draw_player_label(
    canvas: pygame.Surface,
    text: str,
    anchor: tuple[float, float],
    color: Rgb,
    *,
    ready: bool | None = None,
    scale: float = 0.9,
    face: Path | None = None,
) -> None:
    """Draw `P#` centred above `anchor`, optional ready/unready checkmark to the right."""
    ax, ay = int(anchor[0]), int(anchor[1])
    styles.draw_text(
        canvas, text, ax, ay, scale, color, align="center", outline=True, face=face
    )
    if ready is None:
        return
    (tw, th), _ = styles.text_size(text, scale, face)
    check_size = max(14, int(th * 0.9))
    draw_checkmark(
        canvas,
        ax + tw // 2 + check_size // 2 + 6,
        ay - th // 2,
        check_size,
        color,
        checked=ready,
    )
