"""The S-shaped path the "too early" text drifts along (refrences/6.png).

Points are fractions of the canvas, traced for Player 1 (left half) from the bottom (where
the text appears) up to the top-left edge (where it has faded out). Player 2 mirrors it.
"""

from __future__ import annotations

import bisect
import math

# (x, y) as fractions of width / height, bottom -> top, traced from the 1728x1117 sketch.
P1_POINTS = [
    (0.234, 0.877),  # where the text sits
    (0.229, 0.824),
    (0.278, 0.765),
    (0.307, 0.680),
    (0.310, 0.609),
    (0.301, 0.582),
    (0.266, 0.562),
    (0.208, 0.560),
    (0.153, 0.566),
    (0.124, 0.551),
    (0.101, 0.515),
    (0.093, 0.448),
    (0.093, 0.394),
    (0.107, 0.345),
    (0.130, 0.313),
    (0.174, 0.291),
    (0.231, 0.264),
    (0.258, 0.242),
    (0.275, 0.192),
    (0.280, 0.125),
    (0.266, 0.097),
    (0.231, 0.072),
    (0.191, 0.058),
    (0.110, 0.045),
]


def _catmull_rom(points, samples_per_segment: int = 16):
    pts = [points[0], *points, points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(samples_per_segment):
            t = k / samples_per_segment
            t2, t3 = t * t, t * t * t
            out.append(
                tuple(
                    0.5
                    * (
                        2 * p1[d]
                        + (-p0[d] + p2[d]) * t
                        + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2
                        + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3
                    )
                    for d in (0, 1)
                )
            )
    out.append(points[-1])
    return out


class FloatPath:
    """Smooth path in pixels; `at(u)` walks it at constant speed for u in [0, 1]."""

    def __init__(self, size: tuple[int, int], player: int, points=P1_POINTS):
        w, h = size
        self.player = player
        norm = [((1 - x) if player == 1 else x, y) for x, y in points]
        self.pts = [(x * w, y * h) for x, y in _catmull_rom(norm)]
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))

    def at(self, u: float) -> tuple[float, float]:
        u = min(1.0, max(0.0, u))
        target = u * self.cum[-1]
        i = min(bisect.bisect_right(self.cum, target), len(self.pts) - 1)
        if i == 0:
            return self.pts[0]
        seg = self.cum[i] - self.cum[i - 1]
        f = 0.0 if seg == 0 else (target - self.cum[i - 1]) / seg
        (ax, ay), (bx, by) = self.pts[i - 1], self.pts[i]
        return ax + (bx - ax) * f, ay + (by - ay) * f


def ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 2


def fade(t: float, start: float = 0.5) -> float:
    """Opacity 1 until `start`, then linear to 0 at t = 1."""
    if t <= start:
        return 1.0
    return max(0.0, 1 - (t - start) / (1 - start))
