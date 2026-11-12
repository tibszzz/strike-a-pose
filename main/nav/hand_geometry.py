"""Shared MediaPipe hand topology and hold-ring geometry."""

from __future__ import annotations

import math
from typing import Sequence

# Nav / results screens track a single primary hand.
NAV_GESTURE_HANDS = 1

# MediaPipe 21-point hand topology (palm + fingers).
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)

# Wrist + finger MCPs — palm center for the hold ring.
PALM_LANDMARKS = (0, 5, 9, 13, 17)


def palm_center(landmarks: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """Palm midpoint from wrist + finger MCPs when present; else landmark centroid."""
    if not landmarks:
        return None
    idxs = [i for i in PALM_LANDMARKS if i < len(landmarks)]
    pts = [landmarks[i] for i in idxs] if len(idxs) >= 2 else list(landmarks)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def hand_ring_radius(box: tuple[float, float, float, float]) -> float:
    """Half the hand-box diagonal."""
    x0, y0, x1, y1 = box
    return 0.5 * math.hypot(x1 - x0, y1 - y0)


def show_hold_ring(progress: float, label: str | None) -> bool:
    """True when the palm hold ring should be visible."""
    return progress > 0 or label == "Thumb_Up"


def primary_landmarks(snap: object | None) -> tuple[tuple[float, float], ...]:
    """Primary-hand landmarks from a gesture snapshot, or empty."""
    if snap is None:
        return ()
    return tuple(getattr(snap, "landmarks", ()) or ())
