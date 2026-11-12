"""Composite paper widgets shared by menu, how-to-play and results pages.

All sizes are design px (see `paper.Frame`); positions come from the mockups.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pygame

from . import paper
from .paper import DESIGN_H, DESIGN_W, INK, INK_SOFT, UI, Frame, PaperStyle
from .sketch import SKETCH_PAPER

ICONS = UI / "icons"
PALM_ICON = ICONS / "palm.png"
FIST_ICON = ICONS / "fist.png"
FIST_BADGE = ICONS / "fist_badge.png"
PALM_CURSOR = ICONS / "palm_cursor.png"
FIST_CURSOR = ICONS / "fist_cursor.png"
THUMB_UP_ICON = ICONS / "thumb_up.png"

# MediaPipe hand landmark index for the index fingertip (hover pointer).
INDEX_FINGERTIP = 8


def pointer(snap: object | None) -> tuple[float, float] | None:
    """Hover point in canvas px: the primary hand's index fingertip."""
    landmarks = getattr(snap, "landmarks", None) if snap is not None else None
    if not landmarks or len(landmarks) <= INDEX_FINGERTIP:
        return None
    return landmarks[INDEX_FINGERTIP]


# --- title strip ---------------------------------------------------------------


def draw_title_strip(
    surface: pygame.Surface,
    frame: Frame,
    title: str,
    *,
    x: float = 120,
    y: float = 82,
    size: float = 84,
    seed: int = 11,
    max_w: float = 1200,
    condense: float = 1.0,
    anchor: str = "topleft",
) -> pygame.Rect:
    """Big marker title on a torn strip with a bit of tape on top.

    (`x`, `y`) is the design-space point the strip's `anchor` corner sits on.
    """
    face = paper.marker(frame, size)
    label = title.upper()
    tw, th = face.size(label)
    tw = round(tw * condense)
    max_px = frame.px(max_w)
    pad_x, pad_y = frame.px(size * 0.45), frame.px(size * 0.16)
    width = min(tw, max_px) + pad_x * 2
    height = round(th * 0.86) + pad_y * 2
    rect = pygame.Rect(0, 0, width, height)
    setattr(rect, anchor, frame.pt(x, y))
    paper.draw_paper(surface, rect, frame, PaperStyle(torn="tblr", jag=6), seed=seed)
    paper.text(
        surface,
        label,
        face,
        INK,
        (rect.x + pad_x, rect.centery + frame.px(size * 0.04)),
        "midleft",
        max_width=max_px,
        condense=condense,
    )
    paper.draw_tape(surface, (rect.x + frame.px(size * 2.9), rect.y + frame.px(4)), frame, seed=seed)
    return rect


# --- menu note button ------------------------------------------------------------


def draw_note_button(
    surface: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    number: int,
    label: str,
    *,
    selected: bool = False,
    seed: int = 0,
    label_size: float = 50,
    progress: float = 0.0,
) -> None:
    """Notebook-page button: punch holes + margin line on the left, number + label.

    `progress` (0–1) fills a bar along the bottom while a fist hold is pressing it.
    """
    style = PaperStyle(
        fill=paper.PAPER_HOVER if selected else paper.PAPER,
        torn="tbr",
        jag=6,
        holes_left=4,
        rule_left=True,
    )
    paper.draw_paper(surface, rect, frame, style, seed=seed)
    x = rect.x + frame.px(48)
    paper.text(surface, f"{number:02d}", paper.hand(frame, 19), INK_SOFT, (x, rect.y + frame.px(12)))
    face = paper.hand(frame, label_size)
    drawn = paper.text(
        surface,
        label,
        face,
        INK,
        (x, rect.centery + frame.px(label_size * 0.12)),
        "midleft",
        max_width=rect.right - x - frame.px(16),
    )
    if selected:
        paper.draw_scribble_underline(
            surface, drawn.x, drawn.right, drawn.bottom + frame.px(2), frame.px(4), seed=seed
        )
    if progress > 0:
        left = rect.x + frame.px(40)
        bar = pygame.Rect(left, rect.bottom - frame.px(16), rect.right - left - frame.px(14), frame.px(8))
        pygame.draw.rect(surface, paper.INK_FAINT, bar, border_radius=bar.height // 2)
        fill = bar.copy()
        fill.width = max(bar.height, round(bar.width * min(1.0, progress)))
        pygame.draw.rect(surface, paper.HOLD_RING, fill, border_radius=bar.height // 2)


def note_row_rects(frame: Frame, labels: Sequence[str], *, top: float = 40, height: float = 132) -> list[pygame.Rect]:
    """Main-menu notes in a row across the top; width follows each label, slight hand-placed jitter."""
    left, right, gap = 62.0, 1490.0, 30.0
    face = paper.hand(Frame(DESIGN_W, DESIGN_H), 50)
    natural = [max(220.0, face.size(label)[0] + 110.0) for label in labels]
    room = right - left - gap * (len(labels) - 1)
    ratio = room / max(1.0, sum(natural))
    widths = [w * ratio for w in natural]
    jitter_y = (0, 7, -3, 9, 2, -5)
    rects = []
    x = left
    for i, w in enumerate(widths):
        y0 = top + jitter_y[i % len(jitter_y)]
        rects.append(frame.rect(x, y0, x + w, y0 + height))
        x += w + gap
    return rects


# --- hint bar --------------------------------------------------------------------


@dataclass(frozen=True)
class Hint:
    icon: Path | None
    heading: str
    sub: str = ""


def draw_hint_bar(
    surface: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    hints: Sequence[Hint],
    *,
    seed: int = 21,
    scale: float = 1.0,
    alpha: int = 255,
) -> None:
    """Bottom strip: [icon heading / sub] | [icon heading / sub].

    Drawn as a Sharpie outline straight on the sketch sheet (no paper fill) so
    it reads as information, not as another paper-note button. `scale` shrinks
    icons + type; `alpha` < 255 fades the outline, icons and text.
    """
    # Fade by mixing ink toward the sketch sheet and scaling icon alpha, rather
    # than blitting a translucent layer (surface alpha on a per-pixel-alpha
    # layer renders as solid black on some display formats).
    a = max(0, min(255, alpha))

    def ink(color: paper.Rgb) -> paper.Rgb:
        return _fade(color, a, SKETCH_PAPER)

    paper.draw_marker_box(surface, rect, frame, ink(INK), seed=seed)
    if not hints:
        return

    slot_w = rect.width / len(hints)
    icon_box = frame.px(62 * scale)
    head_face = paper.hand(frame, 31 * scale)
    sub_face = paper.hand(frame, 22 * scale)
    for i, hint in enumerate(hints):
        left = rect.x + round(i * slot_w)
        if i:
            pygame.draw.line(
                surface,
                ink(paper.INK_FAINT),
                (left, rect.y + frame.px(20)),
                (left, rect.bottom - frame.px(20)),
                max(1, frame.px(1.5)),
            )
        x = left + frame.px(34 * scale)
        if hint.icon is not None:
            box = pygame.Rect(x, rect.centery - icon_box // 2, icon_box, icon_box)
            paper.blit_art(surface, hint.icon, box, alpha=a)
            x = box.right + frame.px(18 * scale)
        max_text = left + round(slot_w) - x - frame.px(14)
        paper.text(surface, hint.heading, head_face, ink(INK), (x, rect.centery + frame.px(2)), "bottomleft", max_width=max_text)
        paper.text(surface, hint.sub, sub_face, ink(INK_SOFT), (x, rect.centery + frame.px(2)), "topleft", max_width=max_text)


def draw_hint_stack(
    surface: pygame.Surface,
    frame: Frame,
    hints: Sequence[Hint],
    *,
    left: float = 50,
    bottom: float = 846,
    text_size: float = 44,
    icon_size: float = 60,
    gap: float = 12,
    alpha: int = 255,
    dim: Sequence[int] = (),
    seed: int = 21,
    backing: int = 0,
) -> list[pygame.Rect]:
    """Hints stacked upward from (left, bottom), design px, each in a black Sharpie box.

    No paper fill, so hints don't look like the paper-note buttons. `backing`
    (0–255) lays a see-through sketch-paper wash inside each box so the ink
    still reads over live camera (ready-up); 0 leaves it clear (menu).
    Icon + heading only (no sub line); every strip gets the widest strip's
    width so they line up. `dim` lists hint indexes drawn faded (e.g. "Fist to
    start" before enough players are ready). Returns the strip rects, top first.
    """
    ground = SKETCH_PAPER
    gap += 10  # outlines overshoot their corners; keep neighbours apart
    if not hints:
        return []
    face = paper.hand(frame, text_size)
    pad_x, pad_y, icon_gap = 24, 12, 18
    text_w = max(face.size(h.heading)[0] for h in hints) / frame.scale
    width = pad_x * 2 + icon_size + icon_gap + text_w
    height = icon_size + pad_y * 2
    rects: list[pygame.Rect] = []
    y = bottom
    for i in range(len(hints) - 1, -1, -1):
        hint = hints[i]
        rect = frame.rect(left, y - height, left + width, y)
        a = alpha if i not in dim else round(alpha * 0.4)
        if backing > 0:
            _wash(surface, rect, ground, backing)
        paper.draw_marker_box(surface, rect, frame, _fade(INK, a, ground), seed=seed + i)
        x = rect.x + frame.px(pad_x)
        if hint.icon is not None:
            box = pygame.Rect(x, rect.centery - frame.px(icon_size) // 2, frame.px(icon_size), frame.px(icon_size))
            paper.blit_art(surface, hint.icon, box, alpha=a)
            x = box.right + frame.px(icon_gap)
        paper.text(surface, hint.heading, face, _fade(INK, a, ground), (x, rect.centery + frame.px(2)), "midleft")
        rects.insert(0, rect)
        y -= height + gap
    return rects


def _wash(surface: pygame.Surface, rect: pygame.Rect, color: paper.Rgb, alpha: int) -> None:
    """See-through fill (per-pixel alpha: surface alpha can render black on some displays)."""
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    layer.fill((*color, max(0, min(255, alpha))))
    surface.blit(layer, rect.topleft)


def _fade(color: paper.Rgb, alpha: int, ground: paper.Rgb = paper.PAPER) -> paper.Rgb:
    """Ink mixed toward `ground`: `alpha` 255 = full ink, 0 = invisible on that ground."""
    a = max(0, min(255, alpha))
    return tuple(round(p + (c - p) * a / 255) for c, p in zip(color, ground))  # type: ignore[return-value]


# --- how-to-play card -------------------------------------------------------------


def draw_step_card(
    surface: pygame.Surface,
    frame: Frame,
    rect: pygame.Rect,
    number: int,
    art_path: Path | None,
    heading: str,
    sub: str,
    *,
    seed: int = 0,
) -> None:
    """Spiral-notebook page: holes on top, red rule, number, illustration, caption."""
    paper.draw_paper(
        surface, rect, frame, PaperStyle(torn="tb", jag=7, holes_top=8, rule_top=True), seed=seed
    )
    paper.text(surface, f"{number:02d}", paper.hand(frame, 22), INK_SOFT, (rect.x + frame.px(26), rect.y + frame.px(52)))
    art_box = pygame.Rect(
        rect.x + frame.px(36),
        rect.y + frame.px(72),
        rect.width - frame.px(72),
        rect.height - frame.px(72 + 150),
    )
    if art_path is not None:
        paper.blit_art(surface, art_path, art_box)
    caption_y = rect.bottom - frame.px(78)
    paper.text(surface, heading, paper.hand(frame, 46), INK, (rect.centerx, caption_y), "midbottom", max_width=rect.width - frame.px(30))
    paper.text(surface, sub, paper.hand(frame, 27), INK_SOFT, (rect.centerx, caption_y + frame.px(4)), "midtop", max_width=rect.width - frame.px(30))


# --- pointer cursor / hold badge --------------------------------------------------


def draw_hold_badge(
    surface: pygame.Surface,
    frame: Frame,
    icon: Path,
    progress: float,
    *,
    at: tuple[float, float],
) -> None:
    """Paper disc + clockwise hold ring + centre glyph (menu cursor / ready-up hands)."""
    x, y = round(at[0]), round(at[1])
    r = frame.px(46)
    shadow = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 90), (r + 6, r + 7), r)
    surface.blit(shadow, (x - r - 4, y - r - 4))
    pygame.draw.circle(surface, paper.PAPER, (x, y), r)
    ring_w = max(2, frame.px(6))
    track = tuple(int(c * 0.75) for c in paper.PAPER)
    pygame.draw.circle(surface, track, (x, y), r, ring_w)
    if progress > 0:
        # pygame arcs run counter-clockwise from 3 o'clock; end at 12 o'clock so
        # the fill grows clockwise from the top.
        end = math.pi / 2
        start = end - math.tau * min(1.0, progress)
        arc = pygame.Rect(x - r, y - r, r * 2, r * 2)
        pygame.draw.arc(surface, paper.HOLD_RING, arc, start, end, ring_w)
    glyph = pygame.Rect(0, 0, round(r * 1.15), round(r * 1.15))
    glyph.center = (x, y)
    paper.blit_art(surface, icon, glyph)


def draw_cursor(
    surface: pygame.Surface,
    frame: Frame,
    snap: object | None,
    progress: float,
    *,
    at: tuple[float, float] | None,
) -> None:
    """Open palm: white hand icon at `at`. Fist (or a hold in progress): paper badge + hold ring.

    `at` is the page's smoothed cursor (`main.nav.cursor.HandCursor`); None draws nothing.
    """
    if at is None:
        return
    label = getattr(snap, "label", None)
    if label != "Closed_Fist" and progress <= 0:
        box = pygame.Rect(0, 0, frame.px(62), frame.px(66))
        box.center = (round(at[0]), round(at[1]))
        paper.blit_art(surface, PALM_CURSOR, box)
        return
    draw_hold_badge(surface, frame, FIST_ICON, progress, at=at)

