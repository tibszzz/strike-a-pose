"""Visual identity: shared brand Theme plus per-game deltas.

Colors are always RGB. OpenCV call sites convert with `bgr()` at the draw edge.
Shrink game deltas over time to unify look without rewriting callers.

Text: change `FONT` (or `Theme.font`) to rebrand every surface — pygame and OpenCV.
OpenCV-style `scale` maps to pixel size via `scale_to_px`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pygame

from main.settings.paths import ASSETS

Rgb = tuple[int, int, int]
Rgba = tuple[int, int, int, int]

# One face for all game text. Point this at another .ttf to rebrand globally.
FONT = ASSETS / "fonts" / "VT323-Regular.ttf"

# Hershey-era callers pass scale (~0.6–2.0); 30px ≈ former duplex at scale 1.0.
_SCALE_TO_PX = 30
_OUTLINE_PAD = 2

_font_cache: dict[tuple[str, int], pygame.font.Font] = {}


def bgr(color: Rgb) -> Rgb:
    """RGB → OpenCV BGR."""
    r, g, b = color
    return (b, g, r)


def scale_to_px(scale: float) -> int:
    return max(8, round(scale * _SCALE_TO_PX))


def load_font(path: Path, size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    key = (str(path), size)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    try:
        font = pygame.font.Font(str(path), size)
    except (FileNotFoundError, OSError):
        font = pygame.font.SysFont("menlo,monaco,courier", size)
    _font_cache[key] = font
    return font


def text_size(
    text: str, scale: float, face: Path | None = None
) -> tuple[tuple[int, int], int]:
    """((width, height_above_baseline), descent) — same shape as cv2.getTextSize."""
    font = load_font(face or FONT, scale_to_px(scale))
    width, _ = font.size(text)
    ascent = font.get_ascent()
    descent = abs(font.get_descent())
    return (width, ascent), descent


def _render_glyph(
    font: pygame.font.Font, text: str, color: Rgb, outline: bool
) -> pygame.Surface:
    glyph = font.render(text, True, color)
    if not outline:
        return glyph
    shade = font.render(text, True, (0, 0, 0))
    pad = _OUTLINE_PAD
    out = pygame.Surface(
        (glyph.get_width() + pad * 2, glyph.get_height() + pad * 2), pygame.SRCALPHA
    )
    for dx in range(-pad, pad + 1):
        for dy in range(-pad, pad + 1):
            if dx or dy:
                out.blit(shade, (pad + dx, pad + dy))
    out.blit(glyph, (pad, pad))
    return out


def _blit_rgba_to_bgr(dst: np.ndarray, surf: pygame.Surface, x: int, y: int) -> None:
    """Alpha-composite an RGBA pygame surface onto a BGR OpenCV image."""
    sw, sh = surf.get_size()
    dh, dw = dst.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(dw, x + sw), min(dh, y + sh)
    if x1 >= x2 or y1 >= y2:
        return
    sx1, sy1 = x1 - x, y1 - y
    sx2, sy2 = sx1 + (x2 - x1), sy1 + (y2 - y1)
    rgba = np.frombuffer(pygame.image.tobytes(surf, "RGBA"), dtype=np.uint8).reshape(
        (sh, sw, 4)
    )
    src = rgba[sy1:sy2, sx1:sx2]
    alpha = src[..., 3:4].astype(np.float32) / 255.0
    if not np.any(alpha):
        return
    src_bgr = src[..., 2::-1].astype(np.float32)
    roi = dst[y1:y2, x1:x2].astype(np.float32)
    dst[y1:y2, x1:x2] = (src_bgr * alpha + roi * (1.0 - alpha)).astype(np.uint8)


def draw_text(
    canvas: np.ndarray | pygame.Surface,
    text: str,
    x: int,
    y: int,
    scale: float = 1.0,
    color: Rgb = (255, 255, 255),
    align: str = "left",
    outline: bool = False,
    *,
    face: Path | None = None,
) -> pygame.Rect:
    """Draw text with baseline at `y`. `color` is RGB. OpenCV canvases are BGR."""
    if not text:
        return pygame.Rect(x, y, 0, 0)
    font = load_font(face or FONT, scale_to_px(scale))
    surf = _render_glyph(font, text, color, outline)
    text_w, _ = font.size(text)
    ascent = font.get_ascent()
    pad = _OUTLINE_PAD if outline else 0
    if align == "center":
        blit_x = x - text_w // 2 - pad
    elif align == "right":
        blit_x = x - text_w - pad
    else:
        blit_x = x - pad
    blit_y = y - ascent - pad

    if isinstance(canvas, pygame.Surface):
        canvas.blit(surf, (blit_x, blit_y))
    else:
        _blit_rgba_to_bgr(canvas, surf, blit_x, blit_y)
    return pygame.Rect(blit_x + pad, blit_y + pad, text_w, ascent)


@dataclass(frozen=True)
class Theme:
    bg: Rgb
    panel: Rgb
    overlay: Rgba
    ink: Rgb
    muted: Rgb
    on_accent: Rgb
    accent: Rgb
    danger: Rgb
    success: Rgb
    warning: Rgb
    player: tuple[Rgb, ...]
    font: Path
    # Shell / shared chrome extras
    hover: Rgb = (220, 220, 220)
    tile_fill: Rgba = (0, 0, 0, 120)
    # Duel extras
    shadow: Rgb = (190, 190, 190)
    shot_bg: Rgb = (255, 133, 133)
    hint: Rgb = (140, 140, 140)
    # Dodgeball ball-speed colors
    ball_fast: Rgb = (255, 80, 80)
    ball_medium: Rgb = (255, 165, 0)
    ball_slow: Rgb = (255, 255, 100)

    def with_overrides(self, **kwargs) -> Theme:
        return replace(self, **kwargs)

    def title_px(self, h: int) -> int:
        return max(36, h // 12)

    def menu_title_px(self, h: int) -> int:
        return max(28, h // 16)

    def body_px(self, h: int) -> int:
        return max(16, h // 28)

    def hint_px(self, h: int) -> int:
        return max(14, h // 36)

    def tile_label_px(self, h: int) -> int:
        return max(16, h // 32)

    def duel_main_px(self, h: int) -> int:
        return int(0.11 * h)

    def duel_label_px(self, h: int) -> int:
        return int(0.042 * h)

    def duel_shot_px(self, h: int) -> int:
        return int(0.05 * h)

    def duel_title_px(self, h: int) -> int:
        return int(0.05 * h)

    def duel_msg_px(self, h: int) -> int:
        return int(0.034 * h)


# Brand seed: shell look (VT323 / yellow accent on dark).
BRAND = Theme(
    bg=(0, 0, 0),
    panel=(30, 30, 30),
    overlay=(0, 0, 0, 160),
    ink=(255, 255, 255),
    muted=(180, 180, 180),
    on_accent=(0, 0, 0),
    accent=(255, 220, 80),
    danger=(255, 80, 80),
    success=(100, 255, 100),
    warning=(255, 165, 0),
    player=(
        (255, 95, 95),
        (70, 175, 255),
        (110, 230, 110),
        (255, 215, 70),
    ),
    font=FONT,
)

SHELL = BRAND.with_overrides(
    overlay=(0, 0, 0, 140),
)

# Duel: white page, black ink (today's look as a delta).
DUEL = BRAND.with_overrides(
    bg=(255, 255, 255),
    panel=(255, 255, 255),
    ink=(0, 0, 0),
    muted=(140, 140, 140),
    hint=(140, 140, 140),
    on_accent=(255, 255, 255),
    accent=(0, 0, 0),
)

# Strike: dark warm bg + orange accent. Stored RGB; OpenCV uses bgr().
# Former BGR BACKGROUND (30,26,24) → RGB (24,26,30); accent #f6ae2d.
STRIKE = BRAND.with_overrides(
    bg=(24, 26, 30),
    panel=(42, 46, 52),
    ink=(255, 255, 255),
    muted=(175, 175, 175),
    accent=(246, 174, 45),  # #f6ae2d
    player=(
        (255, 95, 95),
        (70, 175, 255),
        (110, 230, 110),
        (255, 215, 70),
    ),
)

# Dodgeball: pygame RGB values as shipped today (accent was the strike BGR tuple used as RGB).
DODGEBALL = BRAND.with_overrides(
    bg=(0, 0, 0),
    ink=(255, 255, 255),
    muted=(175, 175, 175),
    accent=(70, 215, 255),
    danger=(255, 80, 80),
    success=(100, 255, 100),
    warning=(255, 255, 100),
    player=(
        (80, 170, 255),
        (255, 80, 80),
        (100, 255, 100),
    ),
    ball_fast=(255, 80, 80),
    ball_medium=(255, 165, 0),
    ball_slow=(255, 255, 100),
)
