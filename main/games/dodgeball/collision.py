"""Ball-vs-body collision geometry. Pure math: no pygame, no camera.

The body is built from confident COCO keypoints only (undetected joints often
sit at (0, 0) and must never count):

- head: a circle around the nose / eyes / ears
- neck, arms, legs: capsules (a segment with a radius) sized to the person
- torso: the shoulder-hip quadrilateral

The ball is tested as a *swept* circle, from where it was last frame to where it
is now, so a fast ball cannot skip over a thin forearm between two frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

Point = tuple[float, float]

_EPS = 1e-9

# COCO-17 indices (kept local so this module has no project imports).
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 11, 12, 13, 14, 15, 16
HEAD_POINTS = (NOSE, L_EYE, R_EYE, L_EAR, R_EAR)

# Limb thickness (capsule radius) as a fraction of the body scale (~shoulder width).
UPPER_ARM_R = 0.16
FOREARM_R = 0.14
THIGH_R = 0.22
SHIN_R = 0.17
NECK_R = 0.16
HAND_REACH = 0.30  # the hand extends past the wrist by this much of the scale
HEAD_R = 0.32
MIN_SCALE = 20.0  # px; keeps far-away / partial detections hittable


# --- primitive geometry -------------------------------------------------------


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Shortest distance from point `p` to the segment a-b (a == b allowed)."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= _EPS:  # degenerate segment: just a point
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _orient(a: Point, b: Point, c: Point) -> float:
    """Twice the signed area of triangle abc (>0 counter-clockwise)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    """`p` (known collinear with a-b) lies within a-b's bounding box."""
    return (
        min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
        and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS
    )


def segments_intersect(a0: Point, a1: Point, b0: Point, b1: Point) -> bool:
    """True if segments a0-a1 and b0-b1 touch or cross (collinear overlap included)."""
    d1 = _orient(b0, b1, a0)
    d2 = _orient(b0, b1, a1)
    d3 = _orient(a0, a1, b0)
    d4 = _orient(a0, a1, b1)
    if ((d1 > _EPS and d2 < -_EPS) or (d1 < -_EPS and d2 > _EPS)) and (
        (d3 > _EPS and d4 < -_EPS) or (d3 < -_EPS and d4 > _EPS)
    ):
        return True
    return (
        (abs(d1) <= _EPS and _on_segment(b0, b1, a0))
        or (abs(d2) <= _EPS and _on_segment(b0, b1, a1))
        or (abs(d3) <= _EPS and _on_segment(a0, a1, b0))
        or (abs(d4) <= _EPS and _on_segment(a0, a1, b1))
    )


def segment_distance(a0: Point, a1: Point, b0: Point, b1: Point) -> float:
    """Shortest distance between two segments (0 when they touch or cross)."""
    if segments_intersect(a0, a1, b0, b1):
        return 0.0
    return min(
        point_segment_distance(a0, b0, b1),
        point_segment_distance(a1, b0, b1),
        point_segment_distance(b0, a0, a1),
        point_segment_distance(b1, a0, a1),
    )


def point_in_polygon(p: Point, polygon: Sequence[Point]) -> bool:
    """Even-odd ray cast. Works for any simple polygon, convex or not.

    Points exactly on an edge may go either way; callers that care add a
    distance-to-edge check.
    """
    n = len(polygon)
    if n < 3:
        return False
    x, y = p
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Half-open rule on y so a vertex shared by two edges is counted once,
        # and horizontal edges (yi == yj) are skipped without dividing by zero.
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


# --- body shapes --------------------------------------------------------------


@dataclass(frozen=True)
class Capsule:
    """All points within `radius` of the segment a-b (a == b gives a circle)."""

    a: Point
    b: Point
    radius: float


@dataclass(frozen=True)
class Body:
    capsules: tuple[Capsule, ...]
    polygons: tuple[tuple[Point, ...], ...]
    points: tuple[Point, ...]  # confident keypoints (centre of mass for bounces)

    @property
    def empty(self) -> bool:
        return not self.capsules and not self.polygons


def build_body(
    xy: Sequence[Sequence[float]],
    conf: Sequence[float] | None,
    box: tuple[float, float, float, float],
    min_conf: float = 0.3,
) -> Body:
    """Head circle, torso quad and limb capsules from the confident keypoints."""
    pts: dict[int, Point] = {}
    for i in range(min(17, len(xy))):
        if conf is not None and float(conf[i]) < min_conf:
            continue
        x, y = float(xy[i][0]), float(xy[i][1])
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        pts[i] = (x, y)

    scale = _body_scale(pts, box)
    capsules: list[Capsule] = []
    polygons: list[tuple[Point, ...]] = []

    def limb(i: int, j: int, frac: float) -> None:
        if i in pts and j in pts:
            capsules.append(Capsule(pts[i], pts[j], frac * scale))

    limb(L_SHOULDER, L_ELBOW, UPPER_ARM_R)
    limb(R_SHOULDER, R_ELBOW, UPPER_ARM_R)
    limb(L_HIP, L_KNEE, THIGH_R)
    limb(R_HIP, R_KNEE, THIGH_R)
    limb(L_KNEE, L_ANKLE, SHIN_R)
    limb(R_KNEE, R_ANKLE, SHIN_R)
    for elbow, wrist in ((L_ELBOW, L_WRIST), (R_ELBOW, R_WRIST)):
        if elbow in pts and wrist in pts:
            capsules.append(Capsule(pts[elbow], _extend(pts[elbow], pts[wrist], HAND_REACH * scale), FOREARM_R * scale))
        elif wrist in pts:  # lone wrist: still a hand
            capsules.append(Capsule(pts[wrist], pts[wrist], FOREARM_R * scale * 1.5))

    torso = [pts[k] for k in (L_SHOULDER, R_SHOULDER, R_HIP, L_HIP) if k in pts]
    if len(torso) == 4:
        polygons.append(tuple(torso))
    # Torso edges as capsules too: covers partial torsos and gives the quad some
    # thickness when the player stands side-on and it collapses to a sliver.
    limb(L_SHOULDER, R_SHOULDER, UPPER_ARM_R)
    limb(L_HIP, R_HIP, THIGH_R)
    limb(L_SHOULDER, L_HIP, UPPER_ARM_R)
    limb(R_SHOULDER, R_HIP, UPPER_ARM_R)

    head = [pts[k] for k in HEAD_POINTS if k in pts]
    if head:
        hx = sum(p[0] for p in head) / len(head)
        hy = sum(p[1] for p in head) / len(head)
        radius = HEAD_R * scale
        if L_EAR in pts and R_EAR in pts:
            radius = max(radius, 0.6 * math.dist(pts[L_EAR], pts[R_EAR]))
        capsules.append(Capsule((hx, hy), (hx, hy), radius))
        shoulders = [pts[k] for k in (L_SHOULDER, R_SHOULDER) if k in pts]
        if shoulders:
            neck = (sum(p[0] for p in shoulders) / len(shoulders), sum(p[1] for p in shoulders) / len(shoulders))
            capsules.append(Capsule((hx, hy), neck, NECK_R * scale))

    if not capsules and not polygons:
        # Detected but no confident joints: fall back to the middle of the box.
        x1, y1, x2, y2 = box
        inset = (x2 - x1) * 0.2
        rect = ((x1 + inset, y1), (x2 - inset, y1), (x2 - inset, y2), (x1 + inset, y2))
        if x2 - x1 > 2 * inset and y2 > y1:
            polygons.append(rect)

    return Body(tuple(capsules), tuple(polygons), tuple(pts.values()))


def _body_scale(pts: dict[int, Point], box: tuple[float, float, float, float]) -> float:
    """Roughly the shoulder width, from whatever is visible."""
    if L_SHOULDER in pts and R_SHOULDER in pts:
        width = math.dist(pts[L_SHOULDER], pts[R_SHOULDER])
        torso = (
            math.dist(pts[L_SHOULDER], pts[L_HIP]) * 0.6 if L_HIP in pts else 0.0
        )
        # Side-on players have narrow shoulders; the torso length keeps the scale sane.
        return max(MIN_SCALE, width, torso)
    if L_HIP in pts and R_HIP in pts:
        return max(MIN_SCALE, math.dist(pts[L_HIP], pts[R_HIP]) * 1.4)
    return max(MIN_SCALE, (box[3] - box[1]) * 0.25)


def _extend(a: Point, b: Point, extra: float) -> Point:
    """`b` pushed further along a->b by `extra` px (unchanged if a == b)."""
    length = math.dist(a, b)
    if length <= _EPS:
        return b
    k = extra / length
    return (b[0] + (b[0] - a[0]) * k, b[1] + (b[1] - a[1]) * k)


def swept_circle_hits(start: Point, end: Point, radius: float, body: Body) -> bool:
    """Does a circle of `radius` moving start->end touch any part of the body?"""
    for cap in body.capsules:
        if segment_distance(start, end, cap.a, cap.b) <= radius + cap.radius:
            return True
    for poly in body.polygons:
        if point_in_polygon(start, poly) or point_in_polygon(end, poly):
            return True
        n = len(poly)
        for i in range(n):
            if segment_distance(start, end, poly[i], poly[(i + 1) % n]) <= radius:
                return True
    return False
