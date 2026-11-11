"""MediaPipe gesture recognition for menu navigation.

`GestureCommandMapper` is pure (no MediaPipe import) so unit tests stay camera-free.
`GestureRecognizerSession` lazy-imports mediapipe and is started/stopped by the shell.

When YOLO people are available, the session crops around wrists, upscales those
patches, runs the recognizer on the enlarged hands, then maps landmarks back to
full-frame coordinates. Full-frame recognition is the fallback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from main.config import ASSETS, from_env
from main.pose import is_wrist_raised
from main.pose.types import KP, Person

from .types import MenuCommand

LABEL_TO_COMMAND: dict[str, MenuCommand] = {
    "Thumb_Up": MenuCommand.MOVE_UP,
    "Thumb_Down": MenuCommand.MOVE_DOWN,
    "Victory": MenuCommand.SELECT,
}

DEFAULT_MODEL = ASSETS / "models" / "gesture_recognizer.task"

# Wrist / elbow pairs for ROI proposals (YOLO COCO-17).
_WRIST_ELBOW = ((KP.L_WRIST, KP.L_ELBOW), (KP.R_WRIST, KP.R_ELBOW))


@dataclass(frozen=True)
class GestureSnapshot:
    """Latest recognizer output for UI and position-based selection."""

    label: str | None
    score: float = 0.0
    hand_box: tuple[float, float, float, float] | None = None  # xmin, ymin, xmax, ymax px
    landmarks: tuple[tuple[float, float], ...] = ()  # image-pixel (x, y)


@dataclass(frozen=True)
class GestureNavConfig:
    model_path: Path = DEFAULT_MODEL
    min_score: float = 0.5
    refractory_ms: int = 350
    # 1 = wrist ROI crop+upscale before MediaPipe; 0 = full frame only.
    roi: int = 1
    roi_size: int = 320  # square side of the upscaled crop fed to MediaPipe
    roi_scale: float = 2.5  # crop side ≈ forearm_length * scale
    roi_min_px: int = 80  # minimum crop side in source pixels
    roi_max: int = 2  # max wrist ROIs tried per frame
    min_wrist_conf: float = 0.35
    # 1 = drop Thumb_Up unless a YOLO wrist near the hand is raised (not at side).
    thumb_gate: int = 1
    thumb_lift_frac: float = 0.08  # wrist must clear elbow by this × torso length
    thumb_match_frac: float = 0.35  # max hand↔wrist distance as × person-box height


def load_gesture_nav_config() -> GestureNavConfig:
    """Env overrides via field names; optional `GESTURE_MODEL_PATH`."""
    import os

    base = from_env(GestureNavConfig)
    gesture_model = os.environ.get("GESTURE_MODEL_PATH", "").strip()
    if not gesture_model:
        return base
    return replace(base, model_path=Path(gesture_model))


@dataclass(frozen=True)
class HandRoi:
    """Axis-aligned crop in full-frame pixel coordinates (inclusive-exclusive)."""

    x0: int
    y0: int
    x1: int
    y1: int
    priority: float = 0.0  # higher = try first (wrist conf / forearm length)

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)


@dataclass
class GestureCommandMapper:
    """Rising-edge label → MenuCommand with refractory after the mapped gesture leaves."""

    min_score: float = 0.5
    refractory_ms: int = 350
    _holding: str | None = field(default=None, init=False, repr=False)
    _left_at_ms: float | None = field(default=None, init=False, repr=False)

    def feed(self, snapshot: GestureSnapshot, timestamp_ms: float) -> MenuCommand | None:
        label = snapshot.label
        effective = (
            label
            if label is not None
            and snapshot.score >= self.min_score
            and label in LABEL_TO_COMMAND
            else None
        )

        if effective is None:
            if self._holding is not None:
                self._left_at_ms = timestamp_ms
                self._holding = None
            return None

        if self._holding is not None:
            self._holding = effective
            return None

        if self._left_at_ms is not None and (timestamp_ms - self._left_at_ms) < self.refractory_ms:
            return None

        self._holding = effective
        self._left_at_ms = None
        return LABEL_TO_COMMAND[effective]

    def reset(self) -> None:
        self._holding = None
        self._left_at_ms = None


def hand_rois_from_people(
    people: Sequence[Person],
    frame_w: int,
    frame_h: int,
    *,
    min_wrist_conf: float = 0.35,
    scale: float = 2.5,
    min_px: int = 80,
    max_rois: int = 2,
) -> list[HandRoi]:
    """Build up to `max_rois` square crops centered near visible wrists."""
    if frame_w <= 0 or frame_h <= 0 or max_rois <= 0:
        return []

    candidates: list[HandRoi] = []
    for person in people:
        for wrist_i, elbow_i in _WRIST_ELBOW:
            if float(person.conf[wrist_i]) < min_wrist_conf:
                continue
            wx, wy = float(person.xy[wrist_i][0]), float(person.xy[wrist_i][1])
            if not (0 <= wx < frame_w and 0 <= wy < frame_h):
                continue

            side = float(min_px)
            cx, cy = wx, wy
            elbow_ok = float(person.conf[elbow_i]) >= min_wrist_conf
            if elbow_ok:
                ex, ey = float(person.xy[elbow_i][0]), float(person.xy[elbow_i][1])
                forearm = math.hypot(wx - ex, wy - ey)
                side = max(side, forearm * scale)
                # Nudge the crop toward the fingers (away from the elbow).
                if forearm > 1e-3:
                    cx = wx + (wx - ex) / forearm * (side * 0.15)
                    cy = wy + (wy - ey) / forearm * (side * 0.15)
            else:
                # No elbow: size from person box height when available.
                box_h = max(0.0, person.box[3] - person.box[1])
                if box_h > 0:
                    side = max(side, box_h * 0.25)

            half = side / 2.0
            x0 = int(round(cx - half))
            y0 = int(round(cy - half))
            x1 = int(round(cx + half))
            y1 = int(round(cy + half))
            x0 = max(0, min(x0, frame_w - 1))
            y0 = max(0, min(y0, frame_h - 1))
            x1 = max(x0 + 1, min(x1, frame_w))
            y1 = max(y0 + 1, min(y1, frame_h))
            # Re-square inside the frame by shrinking the longer side if clipped.
            w, h = x1 - x0, y1 - y0
            side_i = min(w, h)
            if side_i < max(16, min_px // 2):
                continue
            x1, y1 = x0 + side_i, y0 + side_i
            priority = float(person.conf[wrist_i]) * side
            candidates.append(HandRoi(x0, y0, x1, y1, priority=priority))

    candidates.sort(key=lambda r: r.priority, reverse=True)
    return candidates[:max_rois]


def prepare_roi(
    image_bgr: np.ndarray, roi: HandRoi, out_size: int
) -> tuple[np.ndarray, float, float]:
    """Crop `roi` and resize to `out_size`×`out_size`.

    Returns `(patch_bgr, scale_x, scale_y)` where
    `full_x = roi.x0 + patch_x / scale_x` (same for y).
    """
    out_size = max(16, int(out_size))
    crop = image_bgr[roi.y0 : roi.y1, roi.x0 : roi.x1]
    if crop.size == 0:
        raise ValueError("empty ROI crop")
    patch = cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_LINEAR)
    scale_x = out_size / float(roi.width)
    scale_y = out_size / float(roi.height)
    return patch, scale_x, scale_y


def remap_snapshot(
    snap: GestureSnapshot, roi: HandRoi, scale_x: float, scale_y: float
) -> GestureSnapshot:
    """Map crop-local landmark / box pixels back into full-frame coordinates."""
    if scale_x <= 0 or scale_y <= 0:
        return snap

    def _map_xy(x: float, y: float) -> tuple[float, float]:
        return (roi.x0 + x / scale_x, roi.y0 + y / scale_y)

    landmarks = tuple(_map_xy(x, y) for x, y in snap.landmarks)
    hand_box = None
    if snap.hand_box is not None:
        x0, y0, x1, y1 = snap.hand_box
        mx0, my0 = _map_xy(x0, y0)
        mx1, my1 = _map_xy(x1, y1)
        hand_box = (mx0, my0, mx1, my1)
    return GestureSnapshot(
        label=snap.label, score=snap.score, hand_box=hand_box, landmarks=landmarks
    )


def _snapshot_rank(snap: GestureSnapshot) -> tuple[bool, float, bool]:
    return (len(snap.landmarks) > 0, snap.score, snap.label is not None)


def _better_snapshot(a: GestureSnapshot, b: GestureSnapshot) -> GestureSnapshot:
    return a if _snapshot_rank(a) >= _snapshot_rank(b) else b


def _hand_anchor(snap: GestureSnapshot) -> tuple[float, float] | None:
    """Prefer MediaPipe wrist (landmark 0); else landmark / box centroid."""
    if snap.landmarks:
        return snap.landmarks[0]
    if snap.hand_box is not None:
        x0, y0, x1, y1 = snap.hand_box
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    return None


def apply_thumb_pose_gate(
    snap: GestureSnapshot,
    people: Sequence[Person] | None,
    *,
    enabled: bool = True,
    min_wrist_conf: float = 0.35,
    lift_frac: float = 0.08,
    match_frac: float = 0.35,
) -> GestureSnapshot:
    """Clear Thumb_Up when the matching YOLO arm is hanging at the side.

    Landmarks stay so menu hover still works. If no people are visible the
    label is left alone (nothing to verify against).
    """
    if not enabled or snap.label != "Thumb_Up" or not people:
        return snap

    raised: list[tuple[Person, tuple[float, float]]] = []
    for person in people:
        for side, wrist_i in (("left", KP.L_WRIST), ("right", KP.R_WRIST)):
            if not is_wrist_raised(
                person, side, min_conf=min_wrist_conf, min_lift_frac=lift_frac
            ):
                continue
            raised.append(
                (person, (float(person.xy[wrist_i][0]), float(person.xy[wrist_i][1])))
            )

    if not raised:
        return replace(snap, label=None, score=0.0)

    anchor = _hand_anchor(snap)
    if anchor is None:
        return snap

    ax, ay = anchor
    for person, (wx, wy) in raised:
        box_h = max(1.0, float(person.box[3]) - float(person.box[1]))
        max_dist = box_h * match_frac
        if math.hypot(ax - wx, ay - wy) <= max_dist:
            return snap
    return replace(snap, label=None, score=0.0)


def _landmarks_to_box_and_pts(
    landmarks: Sequence, width: int, height: int
) -> tuple[tuple[float, float, float, float], tuple[tuple[float, float], ...]]:
    xs: list[float] = []
    ys: list[float] = []
    pts: list[tuple[float, float]] = []
    for lm in landmarks:
        x = float(lm.x) * width
        y = float(lm.y) * height
        xs.append(x)
        ys.append(y)
        pts.append((x, y))
    box = (min(xs), min(ys), max(xs), max(ys))
    return box, tuple(pts)


def _empty_snapshot() -> GestureSnapshot:
    return GestureSnapshot(label=None, score=0.0)


class GestureRecognizerSession:
    """Shell-owned MediaPipe Gesture Recognizer with explicit start/stop."""

    def __init__(self, config: GestureNavConfig | None = None) -> None:
        self.config = config or load_gesture_nav_config()
        self._recognizer = None
        self._active = False
        self._last_ts_ms = -1

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        if self._active:
            return
        path = Path(self.config.model_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Gesture recognizer model not found at {path}. "
                "Expected assets/models/gesture_recognizer.task (vendored with the repo)."
            )
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
            VisionTaskRunningMode,
        )
        from mediapipe.tasks.python.vision.gesture_recognizer import (
            GestureRecognizer,
            GestureRecognizerOptions,
        )

        options = GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=VisionTaskRunningMode.VIDEO,
            num_hands=2,
        )
        self._recognizer = GestureRecognizer.create_from_options(options)
        self._active = True
        self._last_ts_ms = -1

    def stop(self) -> None:
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None
        self._active = False
        self._last_ts_ms = -1

    def close(self) -> None:
        self.stop()

    def recognize(
        self,
        image_bgr: np.ndarray,
        timestamp_ms: int,
        people: Sequence[Person] | None = None,
    ) -> GestureSnapshot:
        if not self._active or self._recognizer is None:
            return _empty_snapshot()

        cfg = self.config
        best = _empty_snapshot()
        if cfg.roi and people:
            h, w = image_bgr.shape[:2]
            rois = hand_rois_from_people(
                people,
                w,
                h,
                min_wrist_conf=cfg.min_wrist_conf,
                scale=cfg.roi_scale,
                min_px=cfg.roi_min_px,
                max_rois=cfg.roi_max,
            )
            for roi in rois:
                patch, scale_x, scale_y = prepare_roi(image_bgr, roi, cfg.roi_size)
                snap = self._recognize_image(patch, timestamp_ms)
                timestamp_ms = self._last_ts_ms + 1
                mapped = remap_snapshot(snap, roi, scale_x, scale_y)
                best = _better_snapshot(best, mapped)
                if best.landmarks and best.label is not None:
                    break

        if best.landmarks:
            return apply_thumb_pose_gate(
                best,
                people,
                enabled=bool(cfg.thumb_gate),
                min_wrist_conf=cfg.min_wrist_conf,
                lift_frac=cfg.thumb_lift_frac,
                match_frac=cfg.thumb_match_frac,
            )

        return apply_thumb_pose_gate(
            self._recognize_image(image_bgr, timestamp_ms),
            people,
            enabled=bool(cfg.thumb_gate),
            min_wrist_conf=cfg.min_wrist_conf,
            lift_frac=cfg.thumb_lift_frac,
            match_frac=cfg.thumb_match_frac,
        )

    def _recognize_image(self, image_bgr: np.ndarray, timestamp_ms: int) -> GestureSnapshot:
        assert self._recognizer is not None
        import mediapipe as mp

        # VIDEO mode requires strictly increasing timestamps.
        if timestamp_ms <= self._last_ts_ms:
            timestamp_ms = self._last_ts_ms + 1
        self._last_ts_ms = timestamp_ms

        rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        best_label: str | None = None
        best_score = 0.0
        best_index = -1
        for i, hand_gestures in enumerate(result.gestures or ()):
            if not hand_gestures:
                continue
            top = hand_gestures[0]
            name = getattr(top, "category_name", None) or getattr(top, "display_name", None)
            score = float(top.score)
            if name and name != "None" and score > best_score:
                best_score = score
                best_label = name
                best_index = i

        if best_index < 0 or not result.hand_landmarks or best_index >= len(result.hand_landmarks):
            # Landmarks without a canned gesture still help menu hover.
            if result.hand_landmarks:
                h, w = image_bgr.shape[:2]
                box, pts = _landmarks_to_box_and_pts(result.hand_landmarks[0], w, h)
                return GestureSnapshot(label=None, score=0.0, hand_box=box, landmarks=pts)
            return GestureSnapshot(label=best_label, score=best_score)

        h, w = image_bgr.shape[:2]
        box, pts = _landmarks_to_box_and_pts(result.hand_landmarks[best_index], w, h)
        return GestureSnapshot(label=best_label, score=best_score, hand_box=box, landmarks=pts)
