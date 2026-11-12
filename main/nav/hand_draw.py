"""Pygame drawers for primary-hand skeleton + palm hold ring."""

from __future__ import annotations

import math
from typing import Sequence

import pygame

from .hand_geometry import (
    HAND_CONNECTIONS,
    hand_ring_radius,
    palm_center,
    primary_landmarks,
    show_hold_ring,
)

# Progress arc — matches strike OpenCV HOLD_FILL (#55dde0).
HOLD_RING_FILL = (85, 221, 224)


def draw_hand_skeleton(
    surface: pygame.Surface,
    landmarks: Sequence[tuple[float, float]],
    color: tuple[int, int, int],
) -> None:
    """Draw MediaPipe hand bones and joints in surface pixel space."""
    if len(landmarks) < 2:
        return
    pts = [(int(round(x)), int(round(y))) for x, y in landmarks]
    for a, b in HAND_CONNECTIONS:
        if a < len(pts) and b < len(pts):
            pygame.draw.line(surface, color, pts[a], pts[b], 2)
    for pt in pts:
        pygame.draw.circle(surface, color, pt, 3)


def draw_hold_ring(
    surface: pygame.Surface,
    center: tuple[float, float],
    radius: float,
    progress: float,
    *,
    track_color: tuple[int, int, int],
    fill_color: tuple[int, int, int] = HOLD_RING_FILL,
) -> None:
    """Faint track circle + bright progress arc around the palm."""
    if radius <= 1:
        return
    cx, cy = int(round(center[0])), int(round(center[1]))
    r = max(4, int(round(radius)))
    track = tuple(int(c * 0.45) for c in track_color)
    pygame.draw.circle(surface, track, (cx, cy), r, 3)
    if progress <= 0:
        return
    # Match OpenCV: start at top (-90°), sweep by progress. pygame arc is radians,
    # counter-clockwise from east; with y-down the visual matches the OpenCV sweep.
    start = -math.pi / 2
    end = start + 2 * math.pi * min(1.0, progress)
    rect = pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)
    pygame.draw.arc(surface, fill_color, rect, start, end, 5)


def draw_primary_hand_hold(
    surface: pygame.Surface,
    snap: object | None,
    progress: float,
    *,
    color: tuple[int, int, int],
) -> None:
    """Primary-hand skeleton, plus palm hold ring when holding."""
    primary = primary_landmarks(snap)
    if not primary:
        return
    draw_hand_skeleton(surface, primary, color)
    label = getattr(snap, "label", None) if snap is not None else None
    if not show_hold_ring(progress, label):
        return
    center = palm_center(primary)
    if center is None:
        return
    box = getattr(snap, "hand_box", None) if snap is not None else None
    radius = hand_ring_radius(box) if box is not None else 40.0
    draw_hold_ring(
        surface,
        center,
        radius,
        progress,
        track_color=color,
        fill_color=HOLD_RING_FILL,
    )
