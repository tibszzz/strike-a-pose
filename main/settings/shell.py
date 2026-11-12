"""Shared UI / shell knobs (gesture nav, canvas size)."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from .env import from_env
from .paths import ASSETS

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

DEFAULT_GESTURE_MODEL = ASSETS / "models" / "gesture_recognizer.task"


@dataclass(frozen=True)
class GestureNavConfig:
    model_path: Path = DEFAULT_GESTURE_MODEL
    min_score: float = 0.5
    refractory_ms: int = 350
    # 1 = wrist ROI crop+upscale before MediaPipe; 0 = full frame only.
    roi: int = 1
    roi_size: int = 320  # square side of the upscaled crop fed to MediaPipe
    roi_scale: float = 2.5  # crop side ≈ forearm_length * scale
    roi_min_px: int = 80  # minimum crop side in source pixels
    roi_max: int = 2  # max wrist ROIs tried per frame
    min_wrist_conf: float = 0.35
    # 1 = ignore hand detection unless a YOLO wrist near the hand is above the elbow.
    raise_gate: int = 1
    raise_lift_frac: float = 0.08  # wrist must clear elbow by this × torso length
    raise_match_frac: float = 0.35  # max hand↔raised-wrist distance as × person-box height
    thumb_hold_s: float = 0.5  # seconds confirm gesture must be held on splash / menu
    # Menu / how-to / results hand cursor (main.nav.cursor).
    # Reach zone around the hand owner's shoulders, in torso lengths, mapped onto
    # the screen — so reach is the same near or far from the camera.
    reach_body: int = 1  # 0 = always use the fixed gains below
    reach_half_w: float = 0.9  # left / right of the shoulders
    reach_top: float = 1.1  # above the shoulder line (top of screen)
    reach_bottom: float = 0.3  # below the shoulder line (bottom of screen)
    cursor_gain: float = 1.3  # no body matched: menu + results offset from centre × gain
    cursor_rel_gain: float = 1.8  # no body matched: how-to hand movement × gain
    cursor_grace_s: float = 0.35  # keep the cursor through hand dropouts this short
    cursor_min_cutoff: float = 1.0  # One-Euro Hz; lower = steadier when still
    cursor_beta: float = 0.02  # One-Euro speed term; higher = less lag when moving
    hold_grace_s: float = 0.2  # fist hold survives label flickers this short
    release_open_s: float = 0.12  # a carried-in fist must open this long to count


def load_gesture_nav_config() -> GestureNavConfig:
    """Env overrides via field names; optional `GESTURE_MODEL_PATH`."""
    base = from_env(GestureNavConfig)
    gesture_model = os.environ.get("GESTURE_MODEL_PATH", "").strip()
    if not gesture_model:
        return base
    return replace(base, model_path=Path(gesture_model))
