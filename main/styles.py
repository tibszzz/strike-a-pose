"""Visual identity: shared brand Theme plus per-game deltas.

Colors are always RGB. OpenCV call sites convert with `bgr()` at the draw edge.
Shrink game deltas over time to unify look without rewriting callers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pygame

from main.settings.paths import ASSETS

Rgb = tuple[int, int, int]
Rgba = tuple[int, int, int, int]

TITLE_FONT = ASSETS / "fonts" / "Monofett-Regular.ttf"
BODY_FONT = ASSETS / "fonts" / "VT323-Regular.ttf"
DISPLAY_FONT = ASSETS / "fonts" / "PixelifySans.ttf"


def bgr(color: Rgb) -> Rgb:
    """RGB → OpenCV BGR."""
    r, g, b = color
    return (b, g, r)


def load_font(path: Path, size: int) -> pygame.font.Font:
    try:
        return pygame.font.Font(str(path), size)
    except (FileNotFoundError, OSError):
        return pygame.font.SysFont("menlo,monaco,courier", size)


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
    title: Path
    body: Path
    display: Path
    # Shell / shared chrome extras
    hand_box: Rgb = (80, 220, 255)
    hover: Rgb = (220, 220, 220)
    hold_track: Rgba = (255, 255, 255, 40)
    hold_fill: Rgba = (255, 220, 80, 200)
    hold_fill_tile: Rgba = (255, 220, 80, 70)
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


# Brand seed: shell look (Monofett / VT323 / yellow accent on dark).
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
    title=TITLE_FONT,
    body=BODY_FONT,
    display=DISPLAY_FONT,
)

SHELL = BRAND.with_overrides(
    overlay=(0, 0, 0, 140),
)

# Duel: white page, black ink, Pixelify display (today's look as a delta).
DUEL = BRAND.with_overrides(
    bg=(255, 255, 255),
    panel=(255, 255, 255),
    ink=(0, 0, 0),
    muted=(140, 140, 140),
    hint=(140, 140, 140),
    on_accent=(255, 255, 255),
    accent=(0, 0, 0),
)

# Strike: dark warm bg + cyan accent. Stored RGB; OpenCV uses bgr().
# Former BGR BACKGROUND (30,26,24) → RGB (24,26,30); ACCENT (70,215,255) → (255,215,70).
STRIKE = BRAND.with_overrides(
    bg=(24, 26, 30),
    panel=(42, 46, 52),
    ink=(255, 255, 255),
    muted=(175, 175, 175),
    accent=(255, 215, 70),
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
