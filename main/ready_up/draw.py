"""Pygame chrome for the shared ready-up page.

Live camera (drawn by the game) with a FIFA-style marker over each player:
"P1" above a down-pointing triangle, grey while waiting and filled with the
player's color once they give a thumbs up. A torn-paper hint strip
bottom-left explains thumbs up to join / fist to start, with live status.
"""

from __future__ import annotations

import pygame

from main import content
from main.ready_up.labels import head_anchor
from main.ready_up.logic import ReadyUp
from main.styles import Theme
from main.ui import paper, widgets
from main.ui.paper import Frame
from main.ui.widgets import Hint

copy = content.ReadyUp

WAITING = (226, 218, 196)  # paper-ish grey for not-yet-ready markers


def draw_ready_up(
    canvas: pygame.Surface,
    ready: ReadyUp,
    *,
    theme: Theme,
    status: str | None = None,
) -> None:
    """Full-bleed camera assumed already on canvas; draw player markers + hint strip.

    `status` replaces the fist hint's live sub-line when given.
    """
    w, h = canvas.get_size()
    frame = Frame(w, h)
    colors = list(theme.player)
    for index, cand in enumerate(ready.eligible):
        anchor = head_anchor(cand.box, cand.nose)
        person = cand.person
        if cand.nose is None and person is not None:
            xy = getattr(person, "xy", None)
            conf = getattr(person, "conf", None)
            if xy is not None and conf is not None:
                anchor = head_anchor(cand.box, person_xy=xy, person_conf=conf)
        draw_player_marker(
            canvas,
            frame,
            f"P{index + 1}",
            anchor,
            colors[index % len(colors)],
            ready=cand.ready,
        )

    widgets.draw_hint_bar(
        canvas,
        frame,
        frame.rect(50, 742, 800, 846),
        (
            Hint(widgets.THUMB_UP_ICON, copy.join_heading, _join_sub(ready)),
            Hint(widgets.FIST_BADGE, copy.start_heading, status or _start_sub(ready)),
        ),
        scale=0.85,
        alpha=235,
    )


def draw_player_marker(
    canvas: pygame.Surface,
    frame: Frame,
    label: str,
    anchor: tuple[float, float],
    color: paper.Rgb,
    *,
    ready: bool,
) -> None:
    """Down-pointing triangle with its tip at `anchor`, player label above it."""
    tip_x, tip_y = round(anchor[0]), round(anchor[1])
    half_w, tri_h = frame.px(30), frame.px(40)
    top = tip_y - tri_h
    points = [(tip_x - half_w, top), (tip_x + half_w, top), (tip_x, tip_y)]
    edge = max(2, frame.px(3.5))
    if ready:
        pygame.draw.polygon(canvas, color, points)
        pygame.draw.polygon(canvas, paper.INK, points, edge)
        label_color, alpha = color, 255
    else:
        pad = edge * 2
        box = pygame.Rect(tip_x - half_w - pad, top - pad, half_w * 2 + pad * 2, tri_h + pad * 2)
        local = [(x - box.x, y - box.y) for x, y in points]
        ghost = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.polygon(ghost, (*paper.INK, 90), local)
        pygame.draw.polygon(ghost, (*WAITING, 200), local, edge)
        canvas.blit(ghost, box.topleft)
        label_color, alpha = WAITING, 210
    paper.outlined_text(
        canvas,
        label,
        paper.marker(frame, 50),
        label_color,
        (tip_x, top - frame.px(4)),
        "midbottom",
        width=max(2, frame.px(3)),
        alpha=alpha,
    )


def _join_sub(ready: ReadyUp) -> str:
    return copy.join_sub if ready.eligible else copy.step_in_sub


def _start_sub(ready: ReadyUp) -> str:
    cfg = ready.config
    if ready.can_start:
        return copy.can_start.format(ready=ready.ready_count)
    template = copy.need_one if cfg.min_players == 1 else copy.need_many
    return template.format(min_players=cfg.min_players)
