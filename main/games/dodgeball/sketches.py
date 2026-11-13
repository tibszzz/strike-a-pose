"""Hand-drawn ball and hearts for Dodgeball, matching the paper / how-to-play art.

Everything is drawn at 4x and smooth-scaled down, so the marker strokes come out
antialiased. Surfaces are cached per size; only the ball's pattern is rotated
per frame (its outline and highlight stay put, like light from the top left).
"""

from __future__ import annotations

import math
import random

import pygame

from main.ui.paper import HEART, INK, PAPER

Rgb = tuple[int, int, int]
_SS = 4  # supersampling factor

# Ball fill per pace: the how-to-play art's red for fast, warmer tones below it.
BALL_FILL: dict[str, Rgb] = {
    "slow": (242, 196, 58),
    "medium": (236, 128, 40),
    "fast": (214, 52, 44),
}
HIGHLIGHT = (255, 250, 238)


def _shade(color: Rgb, k: float) -> Rgb:
    return tuple(max(0, min(255, round(c * k))) for c in color)  # type: ignore[return-value]


def _stroke(surface: pygame.Surface, pts: list[tuple[float, float]], color, width: float) -> None:
    """Round-capped marker polyline (on the supersampled surface)."""
    w = max(1, round(width))
    if len(pts) > 1:
        pygame.draw.lines(surface, color, False, pts, w)
    r = w / 2
    for x, y in pts:
        pygame.draw.circle(surface, color, (x, y), r)


def _wobbly_loop(
    cx: float, cy: float, radius_at, rng: random.Random, steps: int = 72, overshoot: float = 0.35
) -> list[tuple[float, float]]:
    """A closed outline drawn in one go: starts anywhere and overshoots the join a little."""
    start = rng.uniform(0, math.tau)
    span = math.tau + overshoot
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = start + span * t
        # Ends drift slightly off the line, so the join reads as hand drawn.
        drift = 1.0 + 0.035 * (t - 0.5) if t > 0.9 or t < 0.1 else 1.0
        r = radius_at(a) * drift
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _circle_mask(surface: pygame.Surface, cx: float, cy: float, r: float) -> None:
    """Keep only the disc of radius `r` (multiplies alpha)."""
    mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), r)
    surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


def _down(surface: pygame.Surface, size: int) -> pygame.Surface:
    out = pygame.transform.smoothscale(surface, (size, size))
    return out.convert_alpha() if pygame.display.get_surface() is not None else out


# --- ball ------------------------------------------------------------------------

_ball_cache: dict[tuple[str, int, str], pygame.Surface] = {}


def _ball_pattern(pace: str, size: int) -> pygame.Surface:
    """Fill, shading hatch and seams: the part that spins."""
    S = size * _SS
    c = S / 2
    R = S * 0.40
    color = BALL_FILL.get(pace, BALL_FILL["medium"])
    rng = random.Random(f"pattern-{pace}")
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(surf, _shade(color, 0.78), (c, c), R)
    pygame.draw.circle(surf, color, (c - R * 0.12, c - R * 0.12), R * 0.92)

    # Diagonal hatching on the shadow side (bottom right).
    hatch = _shade(color, 0.62)
    for k in range(5):
        off = R * (0.15 + 0.17 * k)
        x0, y0 = c + off * 0.9, c + R
        x1, y1 = c + R, c + off * 0.9
        jitter = rng.uniform(-R * 0.04, R * 0.04)
        _stroke(surf, [(x0 + jitter, y0), (x1, y1 + jitter)], hatch, R * 0.07)

    # Two curved seams across the ball, like the playground ball in the art.
    seam_w = R * 0.08
    for bend, tilt in ((0.55, -0.35), (-0.5, -0.35)):
        pts = []
        for i in range(13):
            t = -1.2 + 2.4 * i / 12
            x = t * R
            y = bend * R * (1 - (t * 0.8) ** 2) + tilt * x
            pts.append((c + x, c + y))
        _stroke(surf, pts, INK, seam_w)

    _circle_mask(surf, c, c, R)
    return _down(surf, size)


def _ball_overlay(pace: str, size: int) -> pygame.Surface:
    """Highlight and the wobbly ink outline: drawn on top, never rotated."""
    S = size * _SS
    c = S / 2
    R = S * 0.40
    rng = random.Random(f"outline-{pace}")
    surf = pygame.Surface((S, S), pygame.SRCALPHA)

    # Short curved highlight on the top-left shoulder.
    hl = [
        (c + R * 0.62 * math.cos(a), c + R * 0.62 * math.sin(a))
        for a in [math.radians(d) for d in range(200, 252, 6)]
    ]
    _stroke(surf, hl, HIGHLIGHT, R * 0.13)
    pygame.draw.circle(surf, HIGHLIGHT, (c - R * 0.18, c - R * 0.52), R * 0.07)

    p1, p2 = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
    loop = _wobbly_loop(
        c, c, lambda a: R * (1 + 0.025 * math.sin(2 * a + p1) + 0.02 * math.sin(3 * a + p2)), rng
    )
    _stroke(surf, loop, INK, R * 0.14)
    return _down(surf, size)


def ball_surfaces(pace: str, size: int) -> tuple[pygame.Surface, pygame.Surface]:
    """(pattern, overlay) for a ball sprite `size` px across."""
    out = []
    for layer, make in (("pattern", _ball_pattern), ("overlay", _ball_overlay)):
        key = (pace, size, layer)
        if key not in _ball_cache:
            _ball_cache[key] = make(pace, size)
        out.append(_ball_cache[key])
    return out[0], out[1]


def draw_ball(
    canvas: pygame.Surface,
    center: tuple[float, float],
    size: int,
    pace: str,
    spin_deg: float,
    velocity: tuple[float, float],
) -> None:
    """Sketched ball at `center`, its seams turned by `spin_deg`, with speed lines behind."""
    cx, cy = center
    _speed_lines(canvas, cx, cy, size, pace, velocity)
    pattern, overlay = ball_surfaces(pace, size)
    turned = pygame.transform.rotate(pattern, spin_deg) if spin_deg else pattern
    canvas.blit(turned, turned.get_rect(center=(round(cx), round(cy))))
    canvas.blit(overlay, overlay.get_rect(center=(round(cx), round(cy))))


def _speed_lines(
    canvas: pygame.Surface, cx: float, cy: float, size: int, pace: str, velocity: tuple[float, float]
) -> None:
    """Short ink dashes trailing the ball, like the motion marks in the art."""
    count = {"slow": 0, "medium": 2, "fast": 3}.get(pace, 0)
    vx, vy = velocity
    speed = math.hypot(vx, vy)
    if count == 0 or speed < 1e-3:
        return
    ux, uy = vx / speed, vy / speed
    nx, ny = -uy, ux
    r = size * 0.40
    length = size * (0.45 if pace == "medium" else 0.7)
    width = max(2, round(size * 0.07))
    spread = (-0.5, 0.5) if count == 2 else (-0.6, 0.0, 0.6)
    for k, s in enumerate(spread):
        gap = r * (1.25 + 0.15 * (k % 2))
        bx, by = cx - ux * gap + nx * s * r, cy - uy * gap + ny * s * r
        ex, ey = bx - ux * length, by - uy * length
        pygame.draw.line(canvas, INK, (bx, by), (ex, ey), width)
        for x, y in ((bx, by), (ex, ey)):
            pygame.draw.circle(canvas, INK, (x, y), width / 2)


# --- hearts ----------------------------------------------------------------------

_heart_cache: dict[tuple[bool, int], pygame.Surface] = {}


def _heart_points(cx: float, cy: float, s: float, rng: random.Random | None = None) -> list[tuple[float, float]]:
    # Smooth, low-frequency wobble (not per-point noise) so the line reads as one marker stroke.
    p1, p2 = (rng.uniform(0, math.tau), rng.uniform(0, math.tau)) if rng is not None else (0.0, 0.0)
    amp = 0.45 if rng is not None else 0.0
    pts = []
    for i in range(64):
        t = math.tau * i / 64
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        j = amp * (math.sin(2 * t + p1) + 0.6 * math.sin(3 * t + p2))
        pts.append((cx + (x + j) * s / 36, cy - (y + j) * s / 36 - s * 0.03))
    return pts


def heart_surface(filled: bool, size: int) -> pygame.Surface:
    """A sketched heart as big as `paper.draw_heart(size)`: red with a highlight, or lost.

    The heart body is ~0.94x `size` wide (like paper.draw_heart, used by High Noon
    and the results page); the surface is padded past that for the marker outline.
    Empty hearts are pale fill + outline only (no scribbled cross).
    """
    key = (filled, size)
    cached = _heart_cache.get(key)
    if cached is not None:
        return cached
    dim = round(size * 1.2)
    S = dim * _SS
    c = S / 2
    s = size * _SS * 1.06
    rng = random.Random(f"heart-{filled}")
    surf = pygame.Surface((S, S), pygame.SRCALPHA)
    body = _heart_points(c, c, s)
    if filled:
        pygame.draw.polygon(surf, HEART, body)
        # Hatch shadow on the lower right, clipped to the heart.
        shade = pygame.Surface((S, S), pygame.SRCALPHA)
        for k in range(4):
            off = s * (0.08 + 0.1 * k)
            _stroke(shade, [(c + off, c + s * 0.5), (c + s * 0.5, c + off - s * 0.1)], _shade(HEART, 0.68), s * 0.045)
        clip = pygame.Surface((S, S), pygame.SRCALPHA)
        pygame.draw.polygon(clip, (255, 255, 255, 255), body)
        shade.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(shade, (0, 0))
        # Highlight on the left lobe.
        hl = [(c - s * 0.30 + s * 0.12 * math.cos(a), c - s * 0.16 + s * 0.12 * math.sin(a)) for a in
              [math.radians(d) for d in range(190, 280, 10)]]
        _stroke(surf, hl, HIGHLIGHT, s * 0.06)
    else:
        # Lost life: pale paper inside so the empty heart still reads over video.
        pygame.draw.polygon(surf, (*PAPER, 170), body)
    outline = _heart_points(c, c, s, rng)
    outline = outline[5:] + outline[:9]  # one stroke that overlaps where it starts
    _stroke(surf, outline, INK, s * 0.075)
    out = _down(surf, dim)
    _heart_cache[key] = out
    return out
