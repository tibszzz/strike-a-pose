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


def is_wrist_raised(
    p: Person,
    side: str,
    *,
    min_conf: float = 0.35,
    min_lift_frac: float = 0.08,
) -> bool:
    """True when the wrist sits clearly above the elbow (hand not hanging at the side).

    Image y grows downward. `min_lift_frac` is a fraction of torso length
    (shoulder→hip) so the margin scales with distance from the camera.
    """
    s_i, e_i, w_i = _ARMS[side]
    hip_i = KP.L_HIP if side == "left" else KP.R_HIP
    if not all(float(p.conf[i]) >= min_conf for i in (e_i, w_i)):
        return False
    elbow_y = float(p.xy[e_i][1])
    wrist_y = float(p.xy[w_i][1])
    torso = 0.0
    if float(p.conf[s_i]) >= min_conf and float(p.conf[hip_i]) >= min_conf:
        torso = abs(float(p.xy[s_i][1]) - float(p.xy[hip_i][1]))
    if torso < 1e-3:
        box_h = max(0.0, float(p.box[3]) - float(p.box[1]))
        torso = box_h if box_h > 1e-3 else 100.0
    return wrist_y < elbow_y - torso * min_lift_frac


def classify(p: Person | None, cfg: GestureConfig = GestureConfig()) -> PoseState:
    if p is None:
        return PoseState.MISSING
    if is_drawn(p, cfg):
        return PoseState.DRAWN
    return PoseState.NEUTRAL
