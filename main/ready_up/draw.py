"""Pygame chrome for the shared ready-up page."""

from __future__ import annotations

from pathlib import Path

import pygame

from main import content, styles
from main.nav.hand_draw import draw_hand_skeleton, draw_hold_ring
from main.nav.hand_geometry import hand_ring_radius, palm_center
from main.ready_up.labels import draw_player_label, head_anchor
from main.ready_up.logic import Candidate, ReadyUp, ReadyUpConfig
from main.styles import Theme

copy = content.ReadyUp


def draw_ready_up(
    canvas: pygame.Surface,
    ready: ReadyUp,
    *,
    theme: Theme,
    status: str | None = None,
    snap: object | None = None,
) -> None:
    """Full-bleed camera assumed already on canvas; draw labels + rules + status.

    With `snap` (the shell's gesture snapshot), each recognised hand gets the
    same skeleton + hold ring as the menu / game-over screens.
    """
    cfg = ready.config
    colors = list(theme.player)
    muted = theme.muted
    for index, cand in enumerate(ready.eligible):
        color = colors[index % len(colors)] if cand.ready else muted
        anchor = head_anchor(cand.box, cand.nose)
        person = cand.person
        if cand.nose is None and person is not None:
            xy = getattr(person, "xy", None)
            conf = getattr(person, "conf", None)
            if xy is not None and conf is not None:
                anchor = head_anchor(cand.box, person_xy=xy, person_conf=conf)
        draw_player_label(
            canvas,
            f"P{index + 1}",
            anchor,
            color,
            ready=cand.ready,
            face=theme.font,
        )

    _draw_rules_card(canvas, cfg, theme)
    message = status if status is not None else _default_status(ready)
    _draw_status(canvas, message, theme)
    _draw_hand_holds(canvas, ready, snap, theme)


def _draw_hand_holds(
    canvas: pygame.Surface, ready: ReadyUp, snap: object | None, theme: Theme
) -> None:
    """Skeleton for every hand in someone's box; hold ring while a gesture counts down."""
    hands = getattr(snap, "hands", ()) or ()
    min_score = ready.config.min_score
    for hand in hands:
        if not hand.landmarks or hand.score < min_score:
            continue
        owner = ready.hand_owner(hand)
        if owner is None:
            continue
        draw_hand_skeleton(canvas, hand.landmarks, theme.accent)
        progress = ready.hold_progress(owner, hand.label)
        if progress is None:
            continue
        center = palm_center(hand.landmarks)
        if center is not None:
            draw_hold_ring(
                canvas, center, hand_ring_radius(hand.box), progress, track_color=theme.accent
            )


def _default_status(ready: ReadyUp) -> str:
    cfg = ready.config
    n = ready.ready_count
    if not ready.eligible:
        return copy.step_in
    if not ready.can_start:
        return copy.need_ready.format(
            ready=n, min_players=cfg.min_players, max_players=cfg.max_players
        )
    return copy.fist_to_start.format(ready=n)


def _draw_status(canvas: pygame.Surface, message: str, theme: Theme) -> None:
    w, h = canvas.get_size()
    band_h = max(48, h // 14)
    band = pygame.Surface((w, band_h), pygame.SRCALPHA)
    band.fill((*theme.bg, 160))
    canvas.blit(band, (0, h - band_h))
    styles.draw_text(
        canvas,
        message,
        w // 2,
        h - band_h // 3,
        0.85,
        theme.accent,
        align="center",
        outline=True,
        face=theme.font,
        h=h,
    )


def _draw_rules_card(canvas: pygame.Surface, cfg: ReadyUpConfig, theme: Theme) -> None:
    w, h = canvas.get_size()
    lines = list(cfg.how_to_lines)
    if not lines and not cfg.pose_stills:
        return

    pad = 24
    still_h = min(120, h // 8) if cfg.pose_stills else 0
    scale = 0.7
    text_lines = lines
    widest = max(
        (styles.text_size(line, scale, theme.font, h=h)[0][0] for line in text_lines),
        default=200,
    )
    title_w = styles.text_size(cfg.title, 1.0, theme.font, h=h)[0][0]
    card_w = min(w - 48, max(widest, title_w, still_h * max(1, len(cfg.pose_stills))) + 64)
    line_h = max(22, styles.scale_to_px(scale, h) + 8)
    card_h = 56 + line_h * len(text_lines) + (still_h + 16 if still_h else 0) + pad
    card_h = min(card_h, h // 2)
    card_x = (w - card_w) // 2
    card_y = max(16, h // 40)

    card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    pygame.draw.rect(card, (*theme.bg, 150), card.get_rect(), border_radius=12)
    canvas.blit(card, (card_x, card_y))

    styles.draw_text(
        canvas,
        cfg.title,
        w // 2,
        card_y + 36,
        1.0,
        theme.accent,
        align="center",
        outline=True,
        face=theme.font,
        h=h,
    )
    y = card_y + 56
    for line in text_lines:
        y += line_h
        styles.draw_text(
            canvas,
            line,
            card_x + 32,
            y,
            scale,
            theme.ink,
            outline=True,
            face=theme.font,
            h=h,
        )

    if cfg.pose_stills and still_h > 0:
        _blit_stills(
            canvas,
            cfg.pose_stills,
            card_x + 32,
            card_y + card_h - still_h - 12,
            card_w - 64,
            still_h,
        )


_still_cache: dict[str, pygame.Surface] = {}


def _blit_stills(
    canvas: pygame.Surface,
    paths: tuple[Path, ...],
    x: int,
    y: int,
    max_w: int,
    height: int,
) -> None:
    if not paths:
        return
    gap = 12
    slot_w = max(40, (max_w - gap * (len(paths) - 1)) // len(paths))
    for i, path in enumerate(paths):
        surf = _load_still(path, slot_w, height)
        if surf is None:
            continue
        canvas.blit(surf, (x + i * (slot_w + gap), y))


def _load_still(path: Path, max_w: int, max_h: int) -> pygame.Surface | None:
    key = f"{path}:{max_w}x{max_h}"
    cached = _still_cache.get(key)
    if cached is not None:
        return cached
    if not path.is_file():
        return None
    try:
        raw = pygame.image.load(str(path)).convert_alpha()
    except pygame.error:
        return None
    rw, rh = raw.get_size()
    scale = min(max_w / max(1, rw), max_h / max(1, rh))
    size = (max(1, int(rw * scale)), max(1, int(rh * scale)))
    surf = pygame.transform.smoothscale(raw, size)
    _still_cache[key] = surf
    return surf
