"""Sketchbook backdrop: the pose model's people drawn as marker stick figures.

Used behind the main menu, how-to-play and results pages instead of the live
camera, so players still see themselves move without the video. Each person
YOLO detects is drawn like the Strike a Pose figure (`games.strike.game.
draw_stick_figure`): torso box, limbs, round joint knobs and a ring head at the
nose, in solid even-width ink (a Sharpie on paper) on a full-screen sheet.

Keypoints are smoothed per person (One-Euro, matched frame to frame by box
centre) so the figure moves steadily instead of shivering with YOLO's jitter.
Joints the model isn't confident about are left out.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np
import pygame
import pygame.gfxdraw

from main.nav.cursor import OneEuro
from main.pose.library import BONES, JOINT_NAMES
from main.ui import paper

SKETCH_PAPER = (239, 234, 219)
SKETCH_PAPER_EDGE = (196, 186, 160)
MARKER = paper.INK

MIN_CONF = 0.35
HEAD_FRAC = 0.2  # head radius as a fraction of torso length (same as Strike a Pose)

_INDEX = {name: i for i, name in enumerate(JOINT_NAMES)}
NOSE = _INDEX["nose"]
L_SHOULDER, R_SHOULDER = _INDEX["left_shoulder"], _INDEX["right_shoulder"]
L_HIP, R_HIP = _INDEX["left_hip"], _INDEX["right_hip"]
BONE_IDX = tuple((_INDEX[a], _INDEX[b]) for a, b in BONES)
BODY_IDX = sorted({i for bone in BONE_IDX for i in bone})

Point = tuple[float, float]


# --- public ---------------------------------------------------------------------


def draw_sketch_backdrop(surface: pygame.Surface, pose: object | None = None) -> None:
    """Paper sheet + a stick figure per person in `pose.people` (a PoseFrame)."""
    _draw_sheet(surface)
    if pose is None:
        return
    people = list(getattr(pose, "people", None) or ())
    w, h = surface.get_size()
    image = getattr(pose, "image", None)
    ih, iw = (image.shape[:2]) if image is not None else (h, w)
    sx, sy = w / max(1, iw), h / max(1, ih)
    t = float(getattr(pose, "timestamp", 0.0))
    figures = [
        (np.asarray(p.xy, np.float32) * (sx, sy), np.asarray(p.conf, np.float32)) for p in people
    ]
    for xy, conf in _smoother.update(figures, t):
        draw_stick_figure(surface, xy, conf)


def reset_smoothing() -> None:
    """Forget tracked figures (tests; or when the camera source changes)."""
    _smoother.reset()


def draw_stick_figure(surface: pygame.Surface, xy: np.ndarray, conf: np.ndarray) -> None:
    """Marker stick figure from (17, 2) keypoints already in surface pixels."""
    ok = [bool(c >= MIN_CONF) for c in conf]
    pts: list[Point] = [(float(x), float(y)) for x, y in xy]
    body = [i for i in BODY_IDX if ok[i]]
    if len(body) < 2:
        return

    head = _head(pts, ok)
    ys = [pts[i][1] for i in body]
    xs = [pts[i][0] for i in body]
    span = max(max(ys) - min(ys), max(xs) - min(xs))
    if head is not None:
        span = max(span, max(ys) - (head[0][1] - head[1]))
    width = max(3, round(span / 46))

    for a, b in BONE_IDX:
        if ok[a] and ok[b]:
            _thick_line(surface, pts[a], pts[b], width)
    knob = width + 1  # joint knobs twice the line width, as in Strike a Pose
    for i in body:
        _disc(surface, pts[i], knob)
    if head is not None:
        _ring(surface, head[0], head[1], width)


# --- smoothing ----------------------------------------------------------------------


@dataclass
class _Track:
    filters: list[OneEuro]
    center: Point
    last_seen: float


@dataclass
class FigureSmoother:
    """Per-person keypoint smoothing; people matched to last frame's by box centre."""

    stale_s: float = 0.5
    min_cutoff: float = 1.5
    beta: float = 0.03
    _tracks: list[_Track] = field(default_factory=list)

    def reset(self) -> None:
        self._tracks.clear()

    def update(self, figures: list[tuple[np.ndarray, np.ndarray]], t: float) -> list[tuple[np.ndarray, np.ndarray]]:
        self._tracks = [tr for tr in self._tracks if t - tr.last_seen <= self.stale_s and tr.last_seen <= t]
        free = list(self._tracks)
        out = []
        for xy, conf in figures:
            seen = xy[conf >= MIN_CONF]
            if len(seen) == 0:
                out.append((xy, conf))
                continue
            center = (float(seen[:, 0].mean()), float(seen[:, 1].mean()))
            spread = float(max(np.ptp(seen[:, 0]), np.ptp(seen[:, 1]), 40.0))
            track = min(free, key=lambda tr: _dist(tr.center, center), default=None)
            if track is None or _dist(track.center, center) > spread * 0.6:
                track = _Track([OneEuro(self.min_cutoff, self.beta) for _ in range(len(xy))], center, t)
                self._tracks.append(track)
            else:
                free.remove(track)
            track.center, track.last_seen = center, t
            smoothed = np.array(
                [track.filters[k]((float(x), float(y)), t) for k, (x, y) in enumerate(xy)], np.float32
            )
            out.append((smoothed, conf))
        return out


_smoother = FigureSmoother()


# --- drawing --------------------------------------------------------------------------

_sheets: dict[tuple[int, int], pygame.Surface] = {}


def _draw_sheet(surface: pygame.Surface) -> None:
    size = surface.get_size()
    sheet = _sheets.get(size)
    if sheet is None:
        w, h = size
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xs - w * 0.5) / (w * 0.62)) ** 2 + ((ys - h * 0.48) / (h * 0.66)) ** 2)
        t = np.clip((d - 0.55) / 0.75, 0.0, 1.0)[..., None] ** 1.6
        lo = np.array(SKETCH_PAPER, np.float32)
        hi = np.array(SKETCH_PAPER_EDGE, np.float32)
        rgb = (lo + (hi - lo) * t).astype(np.uint8)
        sheet = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        paper._grain(sheet, random.Random(97), amount=6)
        _sheets[size] = sheet
    surface.blit(sheet, (0, 0))


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mid(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _head(pts: list[Point], ok: list[bool]) -> tuple[Point, float] | None:
    """Ring head like Strike a Pose: at the nose, radius 0.2 × torso length."""
    shoulders_ok = ok[L_SHOULDER] and ok[R_SHOULDER]
    hips_ok = ok[L_HIP] and ok[R_HIP]
    if not shoulders_ok:
        return None
    shoulders = _mid(pts[L_SHOULDER], pts[R_SHOULDER])
    shoulder_w = _dist(pts[L_SHOULDER], pts[R_SHOULDER])
    if hips_ok:
        hips = _mid(pts[L_HIP], pts[R_HIP])
        torso = _dist(shoulders, hips)
        radius = HEAD_FRAC * torso
        up = ((shoulders[0] - hips[0]) / (torso or 1), (shoulders[1] - hips[1]) / (torso or 1))
    else:
        radius = 0.35 * shoulder_w  # hips out of frame (standing close)
        up = (0.0, -1.0)
    radius = max(radius, 6.0)
    if ok[NOSE]:
        return pts[NOSE], radius
    lift = max(0.7 * shoulder_w, 1.6 * radius)
    return (shoulders[0] + up[0] * lift, shoulders[1] + up[1] * lift), radius


def _thick_line(surface: pygame.Surface, a: Point, b: Point, width: int) -> None:
    length = _dist(a, b)
    if length < 0.5:
        return
    nx, ny = -(b[1] - a[1]) / length * width / 2, (b[0] - a[0]) / length * width / 2
    quad = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    pygame.gfxdraw.aapolygon(surface, quad, MARKER)
    pygame.gfxdraw.filled_polygon(surface, quad, MARKER)
    _disc(surface, a, width / 2)  # round caps
    _disc(surface, b, width / 2)


def _disc(surface: pygame.Surface, c: Point, r: float) -> None:
    x, y, rr = round(c[0]), round(c[1]), max(1, round(r))
    pygame.gfxdraw.aacircle(surface, x, y, rr, MARKER)
    pygame.gfxdraw.filled_circle(surface, x, y, rr, MARKER)


def _ring(surface: pygame.Surface, c: Point, r: float, width: int) -> None:
    x, y = round(c[0]), round(c[1])
    outer = max(2, round(r + width / 2))
    inner = max(1, round(r - width / 2))
    pygame.draw.circle(surface, MARKER, (x, y), outer, outer - inner + 1)
    pygame.gfxdraw.aacircle(surface, x, y, outer, MARKER)
    if inner > 1:
        pygame.gfxdraw.aacircle(surface, x, y, inner, MARKER)
