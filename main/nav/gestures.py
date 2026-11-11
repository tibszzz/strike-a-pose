"""MediaPipe gesture recognition for menu navigation.

`GestureCommandMapper` is pure (no MediaPipe import) so unit tests stay camera-free.
`GestureRecognizerSession` lazy-imports mediapipe and is started/stopped by the shell.

When YOLO people are available, the session only considers wrists raised above
the hip: it crops those regions, upscales, runs the recognizer, then maps
landmarks back to full-frame coordinates. If people are visible but no wrists
are raised, recognition is skipped (no full-frame fallback).
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
    # 1 = ignore hand detection unless a YOLO wrist near the hand is above the hip.
    raise_gate: int = 1
    raise_lift_frac: float = 0.08  # wrist must clear hip by this × torso length
    raise_match_frac: float = 0.35  # max hand↔raised-wrist distance as × person-box height
    thumb_hold_s: float = 1.0  # seconds Thumb_Up must be held on splash / menu confirm


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


def any_raised_wrists(
    people: Sequence[Person],
    *,
    min_wrist_conf: float = 0.35,
    lift_frac: float = 0.08,
) -> bool:
    """True when any YOLO wrist sits clearly above its hip."""
    for person in people:
        for side in ("left", "right"):
            if is_wrist_raised(
                person, side, min_conf=min_wrist_conf, min_lift_frac=lift_frac
            ):
                return True
    return False


def hand_rois_from_people(
    people: Sequence[Person],
    frame_w: int,
    frame_h: int,
    *,
    min_wrist_conf: float = 0.35,
    scale: float = 2.5,
    min_px: int = 80,
    max_rois: int = 2,
    lift_frac: float = 0.08,
) -> list[HandRoi]:
    """Build up to `max_rois` square crops centered near wrists raised above the hip."""
    if frame_w <= 0 or frame_h <= 0 or max_rois <= 0:
        return []

    candidates: list[HandRoi] = []
    for person in people:
        for wrist_i, elbow_i in _WRIST_ELBOW:
            side = "left" if wrist_i == KP.L_WRIST else "right"
            if not is_wrist_raised(
                person, side, min_conf=min_wrist_conf, min_lift_frac=lift_frac
            ):
                continue
            wx, wy = float(person.xy[wrist_i][0]), float(person.xy[wrist_i][1])
            if not (0 <= wx < frame_w and 0 <= wy < frame_h):
                continue

            side_px = float(min_px)
            cx, cy = wx, wy
            elbow_ok = float(person.conf[elbow_i]) >= min_wrist_conf
            if elbow_ok:
                ex, ey = float(person.xy[elbow_i][0]), float(person.xy[elbow_i][1])
                forearm = math.hypot(wx - ex, wy - ey)
                side_px = max(side_px, forearm * scale)
                # Nudge the crop toward the fingers (away from the elbow).
                if forearm > 1e-3:
                    cx = wx + (wx - ex) / forearm * (side_px * 0.15)
                    cy = wy + (wy - ey) / forearm * (side_px * 0.15)
            else:
                # No elbow: size from person box height when available.
                box_h = max(0.0, person.box[3] - person.box[1])
                if box_h > 0:
                    side_px = max(side_px, box_h * 0.25)

            half = side_px / 2.0
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
            priority = float(person.conf[wrist_i]) * side_px
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


def pick_gesture_snapshot(
    candidates: Sequence[GestureSnapshot],
    sticky_anchor: tuple[float, float] | None,
    *,
    max_dist: float,
) -> tuple[GestureSnapshot, tuple[float, float] | None]:
    """Choose a hand snapshot, sticky on Thumb_Up until that hand loses it.

    While `sticky_anchor` is set, any Thumb_Up whose wrist/anchor stays within
    `max_dist` of that point wins over higher-scoring other hands. Only when no
    such Thumb_Up remains do we fall back to normal ranking (and clear sticky
    unless the new winner is also Thumb_Up).
    """
    nonempty = [
        c
        for c in candidates
        if c.label is not None or c.landmarks or c.hand_box is not None
    ]
    if not nonempty:
        return _empty_snapshot(), None

    if sticky_anchor is not None and max_dist > 0:
        sticky_thumbs: list[GestureSnapshot] = []
        for c in nonempty:
            if c.label != "Thumb_Up":
                continue
            anchor = _hand_anchor(c)
            if anchor is None:
                continue
            if math.hypot(anchor[0] - sticky_anchor[0], anchor[1] - sticky_anchor[1]) <= max_dist:
                sticky_thumbs.append(c)
        if sticky_thumbs:
            best = sticky_thumbs[0]
            for c in sticky_thumbs[1:]:
                best = _better_snapshot(best, c)
            return best, (_hand_anchor(best) or sticky_anchor)

    best = nonempty[0]
    for c in nonempty[1:]:
        best = _better_snapshot(best, c)
    if best.label == "Thumb_Up":
        return best, _hand_anchor(best)
    return best, None


def apply_raised_arm_gate(
    snap: GestureSnapshot,
    people: Sequence[Person] | None,
    *,
    enabled: bool = True,
    min_wrist_conf: float = 0.35,
    lift_frac: float = 0.08,
    match_frac: float = 0.35,
) -> GestureSnapshot:
    """Drop hand detection unless the hand sits near a YOLO wrist above the hip.

    Clears label, score, landmarks, and hand_box together. If no people are
    visible the snapshot is left alone (nothing to verify against).
    """
    if not enabled or not people:
        return snap
    if snap.label is None and not snap.landmarks and snap.hand_box is None:
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
        return _empty_snapshot()

    anchor = _hand_anchor(snap)
    if anchor is None:
        return _empty_snapshot()

    ax, ay = anchor
    for person, (wx, wy) in raised:
        box_h = max(1.0, float(person.box[3]) - float(person.box[1]))
        max_dist = box_h * match_frac
        if math.hypot(ax - wx, ay - wy) <= max_dist:
            return snap
    return _empty_snapshot()


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
        # Wrist/anchor of the hand currently holding Thumb_Up; prefer it until gone.
        self._thumb_sticky_anchor: tuple[float, float] | None = None

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
        self._thumb_sticky_anchor = None

    def stop(self) -> None:
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None
        self._active = False
        self._last_ts_ms = -1
        self._thumb_sticky_anchor = None

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
        gate_kw = dict(
            enabled=bool(cfg.raise_gate),
            min_wrist_conf=cfg.min_wrist_conf,
            lift_frac=cfg.raise_lift_frac,
            match_frac=cfg.raise_match_frac,
        )

        # People visible with arms down: skip MediaPipe entirely (no full-frame).
        if people and cfg.raise_gate and not any_raised_wrists(
            people, min_wrist_conf=cfg.min_wrist_conf, lift_frac=cfg.raise_lift_frac
        ):
            self._thumb_sticky_anchor = None
            return _empty_snapshot()

        h, w = image_bgr.shape[:2]
        sticky_max_dist = max(40.0, math.hypot(w, h) * 0.15)
        candidates: list[GestureSnapshot] = []

        if cfg.roi and people:
            rois = hand_rois_from_people(
                people,
                w,
                h,
                min_wrist_conf=cfg.min_wrist_conf,
                scale=cfg.roi_scale,
                min_px=cfg.roi_min_px,
                max_rois=cfg.roi_max,
                lift_frac=cfg.raise_lift_frac,
            )
            for roi in rois:
                patch, scale_x, scale_y = prepare_roi(image_bgr, roi, cfg.roi_size)
                for snap in self._recognize_hands(patch, timestamp_ms):
                    candidates.append(remap_snapshot(snap, roi, scale_x, scale_y))
                timestamp_ms = self._last_ts_ms + 1

        if not candidates:
            candidates.extend(self._recognize_hands(image_bgr, timestamp_ms))

        best, sticky = pick_gesture_snapshot(
            candidates,
            self._thumb_sticky_anchor,
            max_dist=sticky_max_dist,
        )
        gated = apply_raised_arm_gate(best, people, **gate_kw)
        if gated.label == "Thumb_Up":
            self._thumb_sticky_anchor = _hand_anchor(gated) or sticky
        else:
            self._thumb_sticky_anchor = None
        return gated

    def _recognize_hands(
        self, image_bgr: np.ndarray, timestamp_ms: int
    ) -> list[GestureSnapshot]:
        """One snapshot per detected hand (label + landmarks when available)."""
        assert self._recognizer is not None
        import mediapipe as mp

        # VIDEO mode requires strictly increasing timestamps.
        if timestamp_ms <= self._last_ts_ms:
            timestamp_ms = self._last_ts_ms + 1
        self._last_ts_ms = timestamp_ms

        rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        hands = list(result.hand_landmarks or ())
        gestures = list(result.gestures or ())
        if not hands and not gestures:
            return []

        h, w = image_bgr.shape[:2]
        out: list[GestureSnapshot] = []
        n = max(len(hands), len(gestures))
        for i in range(n):
            label: str | None = None
            score = 0.0
            if i < len(gestures) and gestures[i]:
                top = gestures[i][0]
                name = getattr(top, "category_name", None) or getattr(top, "display_name", None)
                if name and name != "None":
                    label = name
                    score = float(top.score)
            if i < len(hands):
                box, pts = _landmarks_to_box_and_pts(hands[i], w, h)
                out.append(
                    GestureSnapshot(label=label, score=score, hand_box=box, landmarks=pts)
                )
            elif label is not None:
                out.append(GestureSnapshot(label=label, score=score))
        return out

    def _recognize_image(self, image_bgr: np.ndarray, timestamp_ms: int) -> GestureSnapshot:
        """Best single-hand snapshot for this image (no Thumb_Up sticky)."""
        hands = self._recognize_hands(image_bgr, timestamp_ms)
        best, _ = pick_gesture_snapshot(hands, None, max_dist=0.0)
        return best
