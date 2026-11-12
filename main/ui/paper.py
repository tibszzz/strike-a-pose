"""Torn-paper look for the menu, how-to-play and results pages.

Everything is laid out in *design space*: the 1552x873 mockups. `Frame` maps a
design rect onto any canvas (scaled to fit, centred), so positions can be read
straight off the mockups. Colors are RGB.

Paper surfaces (torn edges, grain, shadow, punch holes) are expensive to build,
so they are cached by size + style; drawing them every frame is just a blit.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame
import pygame.gfxdraw

from main.settings.paths import ASSETS

Rgb = tuple[int, int, int]

DESIGN_W, DESIGN_H = 1552, 873

FONTS = ASSETS / "fonts"
UI = ASSETS / "ui"
MARKER_FONT = FONTS / "PermanentMarker-Regular.ttf"
HAND_FONT = FONTS / "PatrickHand-Regular.ttf"

# --- tokens ------------------------------------------------------------------

BACKDROP = (42, 40, 30)
BACKDROP_GLOW = (58, 50, 36)
PAPER = (219, 208, 177)
PAPER_HOVER = (236, 219, 164)
INK = (38, 38, 30)
INK_SOFT = (92, 86, 70)
INK_FAINT = (150, 140, 112)
MARGIN_LINE = (212, 150, 128)
TAPE = (196, 182, 136)
HOLD_RING = (176, 138, 62)
HIGHLIGHT = (246, 206, 92)
VIDEO_SHADE = (24, 20, 12, 120)

# Player colors that read on paper (P1 red, P2 blue, P3 green, P4 orange).
PLAYER_INK: tuple[Rgb, ...] = (
    (214, 72, 56),
    (52, 112, 204),
    (58, 150, 72),
    (226, 150, 34),
)
# Dodgeball's in-game labels run blue, red, green, yellow; keep its results in step.
PLAYER_INK_DODGEBALL: tuple[Rgb, ...] = (
    (52, 112, 204),
    (214, 72, 56),
    (58, 150, 72),
    (226, 150, 34),
)
HEART = (210, 58, 50)


def player_ink(player: int, palette: tuple[Rgb, ...] = PLAYER_INK) -> Rgb:
    """Color for 1-based player number."""
    return palette[(player - 1) % len(palette)]


# --- design-space frame --------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """Maps 1552x873 design coordinates onto a w x h canvas (fit + centre)."""

    w: int
    h: int

    @property
    def scale(self) -> float:
        return min(self.w / DESIGN_W, self.h / DESIGN_H)

    @property
    def ox(self) -> float:
        return (self.w - DESIGN_W * self.scale) / 2

    @property
    def oy(self) -> float:
        return (self.h - DESIGN_H * self.scale) / 2

    def px(self, v: float) -> int:
        return max(1, round(v * self.scale))

    def pt(self, x: float, y: float) -> tuple[int, int]:
        return (round(self.ox + x * self.scale), round(self.oy + y * self.scale))

    def rect(self, x0: float, y0: float, x1: float, y1: float) -> pygame.Rect:
        left, top = self.pt(x0, y0)
        right, bottom = self.pt(x1, y1)
        return pygame.Rect(left, top, max(1, right - left), max(1, bottom - top))


# --- fonts + text ---------------------------------------------------------------

_fonts: dict[tuple[str, int], pygame.font.Font] = {}


def font(path: Path, px: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    px = max(8, int(px))
    key = (str(path), px)
    cached = _fonts.get(key)
    if cached is None:
        try:
            cached = pygame.font.Font(str(path), px)
        except (FileNotFoundError, OSError):
            cached = pygame.font.SysFont("chalkboard,comic sans ms,arial", px)
        _fonts[key] = cached
    return cached


def marker(frame: Frame, design_px: float) -> pygame.font.Font:
    return font(MARKER_FONT, frame.px(design_px))


def hand(frame: Frame, design_px: float) -> pygame.font.Font:
    return font(HAND_FONT, frame.px(design_px))


def text(
    surface: pygame.Surface,
    value: str,
    face: pygame.font.Font,
    color: Rgb,
    pos: tuple[float, float],
    anchor: str = "topleft",
    max_width: int | None = None,
    condense: float = 1.0,
    alpha: int = 255,
) -> pygame.Rect:
    """Blit `value` with `anchor` (any pygame.Rect attribute) at `pos`.

    `condense` < 1 squeezes glyphs horizontally; `max_width` shrinks to fit;
    `alpha` < 255 fades the glyphs.
    """
    glyphs = face.render(value, True, color)
    if alpha < 255:
        # Scale per-pixel alpha (surface alpha on SRCALPHA can render black on some displays).
        glyphs = glyphs.convert_alpha() if pygame.display.get_surface() is not None else glyphs
        glyphs.fill((255, 255, 255, max(0, alpha)), special_flags=pygame.BLEND_RGBA_MULT)
    if condense != 1.0:
        glyphs = pygame.transform.smoothscale(
            glyphs, (max(1, round(glyphs.get_width() * condense)), glyphs.get_height())
        )
    if max_width is not None and glyphs.get_width() > max_width > 0:
        ratio = max_width / glyphs.get_width()
        glyphs = pygame.transform.smoothscale(
            glyphs, (max_width, max(1, int(glyphs.get_height() * ratio)))
        )
    rect = glyphs.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surface.blit(glyphs, rect)
    return rect


# --- art -----------------------------------------------------------------------

_art: dict[tuple[str, int, int], pygame.Surface | None] = {}


def art(path: Path, max_w: int, max_h: int) -> pygame.Surface | None:
    """Load a PNG scaled to fit max_w x max_h (aspect kept). None if missing."""
    key = (str(path), max_w, max_h)
    if key in _art:
        return _art[key]
    surf: pygame.Surface | None = None
    if path.is_file():
        try:
            raw = pygame.image.load(str(path))
            if pygame.display.get_surface() is not None:
                raw = raw.convert_alpha()
            rw, rh = raw.get_size()
            ratio = min(max_w / max(1, rw), max_h / max(1, rh))
            size = (max(1, round(rw * ratio)), max(1, round(rh * ratio)))
            surf = pygame.transform.smoothscale(raw, size)
        except pygame.error:
            surf = None
    _art[key] = surf
    return surf


_faded: dict[tuple[str, int, int, int], pygame.Surface] = {}


def blit_art(
    surface: pygame.Surface, path: Path, box: pygame.Rect, anchor: str = "center", alpha: int = 255
) -> pygame.Rect | None:
    """Blit art fitted into `box`. `alpha` < 255 fades it (per-pixel alpha scaled, cached)."""
    img = art(path, box.width, box.height)
    if img is None:
        return None
    if alpha < 255:
        key = (str(path), box.width, box.height, alpha)
        faded = _faded.get(key)
        if faded is None:
            faded = img.convert_alpha() if pygame.display.get_surface() is not None else img.copy()
            faded.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
            _faded[key] = faded
        img = faded
    rect = img.get_rect(**{anchor: getattr(box, anchor)})
    surface.blit(img, rect)
    return rect


# --- paper ---------------------------------------------------------------------


def _torn_polygon(
    w: int, h: int, rng: random.Random, jag: float, torn: str
) -> list[tuple[float, float]]:
    """Outline of a w x h sheet; edges named in `torn` ("tblr") get ragged."""
    step = max(4.0, jag * 1.6)
    soft = jag * 0.25

    def edge(x0, y0, x1, y1, amount, inward):
        length = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(length / step))
        pts = []
        for i in range(n):
            t = i / n
            off = rng.uniform(0, amount)
            pts.append((x0 + (x1 - x0) * t + inward[0] * off, y0 + (y1 - y0) * t + inward[1] * off))
        return pts

    top = edge(0, 0, w, 0, jag if "t" in torn else soft, (0, 1))
    right = edge(w, 0, w, h, jag if "r" in torn else soft, (-1, 0))
    bottom = edge(w, h, 0, h, jag if "b" in torn else soft, (0, -1))
    left = edge(0, h, 0, 0, jag if "l" in torn else soft, (1, 0))
    return top + right + bottom + left


def _grain(surf: pygame.Surface, rng: random.Random, amount: int = 5) -> None:
    """Fine paper fibre noise plus soft blotches (alpha untouched)."""
    w, h = surf.get_size()
    gen = np.random.default_rng(rng.randrange(1 << 30))
    noise = gen.integers(-amount, amount + 1, (w, h)).astype(np.int16)
    # Soft low-frequency mottling: tiny random field, smoothly upscaled.
    sw, sh = max(2, w // 60), max(2, h // 60)
    field = gen.integers(0, 256, (sw, sh, 3)).astype(np.uint8)
    field[..., 1] = field[..., 0]
    field[..., 2] = field[..., 0]
    small = pygame.surfarray.make_surface(field)
    blot = pygame.surfarray.array3d(pygame.transform.smoothscale(small, (w, h)))[..., 0].astype(np.int16)
    blot = (blot - 128) * amount // 128
    rgb = pygame.surfarray.pixels3d(surf)
    shaded = rgb.astype(np.int16) + (noise + blot)[..., None]
    rgb[...] = np.clip(shaded, 0, 255).astype(np.uint8)
    del rgb


@dataclass(frozen=True)
class PaperStyle:
    fill: Rgb = PAPER
    torn: str = "tb"  # which edges are ragged
    jag: float = 7.0  # design px
    holes_top: int = 0  # punch holes along the top (how-to cards)
    holes_left: int = 0  # punch holes down the left (menu notes)
    rule_top: bool = False  # faint red rule under the top holes
    rule_left: bool = False  # faint margin line right of the left holes
    shadow: bool = True


_paper: dict[tuple, pygame.Surface] = {}


def paper_surface(
    size: tuple[int, int], frame: Frame, style: PaperStyle, seed: int
) -> tuple[pygame.Surface, tuple[int, int]]:
    """A paper sheet of `size` px. Returns (surface, offset to blit at rect.topleft)."""
    w, h = max(4, size[0]), max(4, size[1])
    key = (w, h, round(frame.scale, 4), style, seed)
    pad = frame.px(14)
    cached = _paper.get(key)
    if cached is not None:
        return cached, (-pad, -pad)

    rng = random.Random(seed)
    jag = max(2.0, style.jag * frame.scale)
    poly = _torn_polygon(w, h, rng, jag, style.torn)
    full = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

    if style.shadow:
        shadow = pygame.Surface(full.get_size(), pygame.SRCALPHA)
        dx, dy = frame.px(3), frame.px(6)
        pygame.draw.polygon(shadow, (0, 0, 0, 120), [(x + pad + dx, y + pad + dy) for x, y in poly])
        sw, sh = shadow.get_size()
        tiny = pygame.transform.smoothscale(shadow, (max(1, sw // 6), max(1, sh // 6)))
        full.blit(pygame.transform.smoothscale(tiny, (sw, sh)), (0, 0))

    sheet = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(sheet, (*style.fill, 255), poly)
    _grain(sheet, rng)

    if style.rule_top:
        y = frame.px(42)
        pygame.draw.line(sheet, (*MARGIN_LINE, 150), (0, y), (w, y), max(1, frame.px(1.5)))
    if style.rule_left:
        x = frame.px(36)
        pygame.draw.line(sheet, (*MARGIN_LINE, 170), (x, 0), (x, h), max(1, frame.px(1.5)))

    hole_r = max(2, frame.px(5.5))
    if style.holes_top:
        y = frame.px(24)
        x0, gap = frame.px(52), frame.px(45.5)
        for i in range(style.holes_top):
            x = x0 + i * gap
            if x < w - frame.px(20):
                pygame.draw.circle(sheet, (*INK, 235), (x, y), hole_r)
    if style.holes_left:
        x = frame.px(16)
        top, bottom = frame.px(20), h - frame.px(20)
        n = style.holes_left
        for i in range(n):
            y = top + (bottom - top) * (i / max(1, n - 1)) if n > 1 else h // 2
            pygame.draw.circle(sheet, (*INK, 220), (x, int(y)), max(2, frame.px(4.5)))

    full.blit(sheet, (pad, pad))
    _paper[key] = full
    if len(_paper) > 256:
        _paper.pop(next(iter(_paper)))
    return full, (-pad, -pad)


def draw_paper(
    surface: pygame.Surface,
    rect: pygame.Rect,
    frame: Frame,
    style: PaperStyle = PaperStyle(),
    seed: int = 0,
) -> None:
    sheet, (dx, dy) = paper_surface(rect.size, frame, style, seed)
    surface.blit(sheet, (rect.x + dx, rect.y + dy))


_tape: dict[tuple, pygame.Surface] = {}


def draw_tape(
    surface: pygame.Surface, center: tuple[int, int], frame: Frame, width: float = 142, height: float = 36, angle: float = -2.0, seed: int = 3
) -> None:
    """Translucent masking tape strip (design-px size), slightly rotated."""
    key = (frame.px(width), frame.px(height), angle, seed)
    strip = _tape.get(key)
    if strip is None:
        w, h = key[0], key[1]
        rng = random.Random(seed)
        poly = _torn_polygon(w, h, rng, max(2.0, frame.px(3)), "lr")
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(base, (*TAPE, 190), poly)
        strip = pygame.transform.rotate(base, angle)
        _tape[key] = strip
    surface.blit(strip, strip.get_rect(center=center))


# --- backdrop ------------------------------------------------------------------

_backdrops: dict[tuple[int, int], pygame.Surface] = {}


def draw_backdrop(surface: pygame.Surface) -> None:
    """Dark warm desk with a soft centre glow (how-to + results pages)."""
    size = surface.get_size()
    bg = _backdrops.get(size)
    if bg is None:
        w, h = size
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xs - w * 0.45) / (w * 0.75)) ** 2 + ((ys - h * 0.5) / (h * 0.8)) ** 2)
        t = np.clip(1.0 - d, 0.0, 1.0)[..., None]
        lo = np.array(BACKDROP, np.float32)
        hi = np.array(BACKDROP_GLOW, np.float32)
        rgb = (lo + (hi - lo) * t).astype(np.uint8)
        bg = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        _backdrops[size] = bg
    surface.blit(bg, (0, 0))


_veils: dict[tuple[int, int], pygame.Surface] = {}


def shade_video(surface: pygame.Surface) -> None:
    """Warm darkening over the live camera so paper notes pop (main menu)."""
    size = surface.get_size()
    veil = _veils.get(size)
    if veil is None:
        veil = pygame.Surface(size, pygame.SRCALPHA)
        veil.fill(VIDEO_SHADE)
        _veils[size] = veil
    surface.blit(veil, (0, 0))


# --- small drawings --------------------------------------------------------------


def draw_heart(surface: pygame.Surface, center: tuple[int, int], size: int, filled: bool) -> None:
    """Hand-drawn style heart: red fill with ink outline, or empty outline."""
    cx, cy = center
    s = max(6, size)
    r = s * 0.27
    pts = []
    for i in range(48):
        t = math.tau * i / 48
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s / 34, cy - y * s / 34 - r * 0.1))
    if filled:
        pygame.draw.polygon(surface, HEART, pts)
    pygame.draw.polygon(surface, INK, pts, max(1, s // 12))


def draw_tag(
    surface: pygame.Surface, label: str, face: pygame.font.Font, color: Rgb, pos: tuple[int, int], anchor: str = "midleft"
) -> pygame.Rect:
    """Colored player tag (P1/P2…) like the mockups: filled box, ink border, paper text."""
    glyphs = face.render(label, True, (250, 246, 236))
    pad_x, pad_y = max(4, glyphs.get_height() // 4), max(1, glyphs.get_height() // 12)
    rect = pygame.Rect(0, 0, glyphs.get_width() + pad_x * 2, glyphs.get_height() + pad_y * 2)
    setattr(rect, anchor, pos)
    radius = max(2, rect.height // 6)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, INK, rect, max(1, rect.height // 14), border_radius=radius)
    surface.blit(glyphs, glyphs.get_rect(center=rect.center))
    return rect


def draw_highlight(surface: pygame.Surface, rect: pygame.Rect, color: Rgb = HIGHLIGHT, alpha: int = 150, seed: int = 0) -> None:
    """Marker-pen highlight stroke behind `rect` (slightly uneven ends)."""
    rng = random.Random(seed)
    w, h = rect.size
    poly = [
        (rng.uniform(0, h * 0.3), rng.uniform(0, h * 0.15)),
        (w - rng.uniform(0, h * 0.3), rng.uniform(0, h * 0.2)),
        (w - rng.uniform(0, h * 0.2), h - rng.uniform(0, h * 0.15)),
        (rng.uniform(0, h * 0.2), h - rng.uniform(0, h * 0.2)),
    ]
    stroke = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(stroke, (*color, alpha), poly)
    surface.blit(stroke, rect.topleft)


def draw_scribble_underline(surface: pygame.Surface, x0: int, x1: int, y: int, width: int, seed: int = 0) -> None:
    """Slightly wobbly ink underline (selected menu note)."""
    rng = random.Random(seed)
    n = max(4, (x1 - x0) // 12)
    pts = [(x0 + (x1 - x0) * i / n, y + rng.uniform(-width * 0.35, width * 0.35)) for i in range(n + 1)]
    pygame.draw.lines(surface, (102, 84, 43), False, pts, width)


_marker_boxes: dict[tuple, pygame.Surface] = {}


def draw_marker_box(
    surface: pygame.Surface,
    rect: pygame.Rect,
    frame: Frame,
    color: Rgb = INK,
    width: float = 3.5,
    seed: int = 0,
) -> None:
    """Hand-drawn Sharpie outline around `rect`: no fill, no shadow.

    Four separate wobbly strokes (`width` design px) that overshoot the corners a
    little, like a box drawn quickly with a marker. Cached per size/style.
    """
    w, h = rect.size
    stroke = max(2, frame.px(width))
    over = frame.px(7)  # corner overshoot
    wob = max(1.0, frame.px(2.2))
    pad = over + stroke + round(wob) + 2
    key = (w, h, round(frame.scale, 4), color, stroke, seed)
    box = _marker_boxes.get(key)
    if box is None:
        rng = random.Random(seed)
        box = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        corners = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
        corners = [(x + rng.uniform(-wob, wob), y + rng.uniform(-wob, wob)) for x, y in corners]
        for i in range(4):
            (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
            length = math.hypot(x1 - x0, y1 - y0) or 1.0
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            start = rng.uniform(0.2, 1.0) * over
            end = rng.uniform(0.2, 1.0) * over
            a = (x0 - ux * start, y0 - uy * start)
            b = (x1 + ux * end, y1 + uy * end)
            # Gentle bow through the middle so edges aren't ruler-straight.
            bow = rng.uniform(-wob, wob)
            n = max(3, int(length / frame.px(18)))
            pts = []
            for k in range(n + 1):
                t = k / n
                off = bow * math.sin(math.pi * t) + rng.uniform(-wob, wob) * 0.25
                pts.append((a[0] + (b[0] - a[0]) * t - uy * off, a[1] + (b[1] - a[1]) * t + ux * off))
            _marker_stroke(box, pts, color, stroke)
        _marker_boxes[key] = box
        if len(_marker_boxes) > 128:
            _marker_boxes.pop(next(iter(_marker_boxes)))
    surface.blit(box, (rect.x - pad, rect.y - pad))


def _marker_stroke(surface: pygame.Surface, pts: list[tuple[float, float]], color: Rgb, width: int) -> None:
    """Antialiased even-width polyline with round caps (joins are shallow, so none)."""
    r = width / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 0.5:
            continue
        nx, ny = -(y1 - y0) / length * r, (x1 - x0) / length * r
        quad = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
        pygame.gfxdraw.aapolygon(surface, quad, color)
        pygame.gfxdraw.filled_polygon(surface, quad, color)
    rr = max(1, round(r))
    for x, y in (pts[0], pts[-1]):
        pygame.gfxdraw.aacircle(surface, round(x), round(y), rr, color)
        pygame.gfxdraw.filled_circle(surface, round(x), round(y), rr, color)


def outlined_text(
    surface: pygame.Surface,
    value: str,
    face: pygame.font.Font,
    color: Rgb,
    pos: tuple[float, float],
    anchor: str = "center",
    outline: Rgb = INK,
    width: int = 3,
    alpha: int = 255,
) -> pygame.Rect:
    """Text with a solid outline so it reads over live video."""
    glyphs = face.render(value, True, color)
    shade = face.render(value, True, outline)
    w = max(1, width)
    out = pygame.Surface((glyphs.get_width() + w * 2, glyphs.get_height() + w * 2), pygame.SRCALPHA)
    for dx in range(-w, w + 1):
        for dy in range(-w, w + 1):
            if dx * dx + dy * dy <= w * w:
                out.blit(shade, (w + dx, w + dy))
    out.blit(glyphs, (w, w))
    if alpha < 255:
        # Scale per-pixel alpha (surface alpha on SRCALPHA can render black on some displays).
        out.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
    rect = out.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surface.blit(out, rect)
    return rect
