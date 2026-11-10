"""Reusable pose classifiers built on COCO keypoints."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from .types import KP, Person


class PoseState(Enum):
    MISSING = "missing"
    DRAWN = "drawn"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class GestureConfig:
    min_conf: float = 0.5
    # Elbow angle in degrees (180 = perfectly straight) needed to count as extended.
    min_elbow_angle: float = 140.0
    # Max angle of the shoulder->wrist line away from horizontal, in degrees.
    max_arm_tilt: float = 30.0


_ARMS = {
    "left": (KP.L_SHOULDER, KP.L_ELBOW, KP.L_WRIST),
    "right": (KP.R_SHOULDER, KP.R_ELBOW, KP.R_WRIST),
}


def _visible(p: Person, idxs, cfg: GestureConfig) -> bool:
    return all(p.conf[i] >= cfg.min_conf for i in idxs)


def _angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    cos = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
    return math.degrees(math.acos(cos))


def is_arm_extended(p: Person, side: str, cfg: GestureConfig = GestureConfig()) -> bool:
    """Arm held out roughly horizontally at shoulder height with a fairly straight elbow."""
    s_i, e_i, w_i = _ARMS[side]
    if not _visible(p, (s_i, e_i, w_i), cfg):
        return False
    s, e, w = p.xy[s_i], p.xy[e_i], p.xy[w_i]
    if _angle_deg(s - e, w - e) < cfg.min_elbow_angle:
        return False
    dx, dy = abs(w[0] - s[0]), abs(w[1] - s[1])
    if dx < 1e-6:
        return False
    return math.degrees(math.atan2(dy, dx)) <= cfg.max_arm_tilt


def is_drawn(p: Person, cfg: GestureConfig = GestureConfig()) -> bool:
    return is_arm_extended(p, "left", cfg) or is_arm_extended(p, "right", cfg)


def classify(p: Person | None, cfg: GestureConfig = GestureConfig()) -> PoseState:
    if p is None:
        return PoseState.MISSING
    if is_drawn(p, cfg):
        return PoseState.DRAWN
    return PoseState.NEUTRAL
