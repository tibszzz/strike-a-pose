"""MediaPipe gesture recognition for menu navigation.

`GestureCommandMapper` is pure (no MediaPipe import) so unit tests stay camera-free.
`GestureRecognizerSession` lazy-imports mediapipe and is started/stopped by the shell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from main.config import ASSETS, from_env

from .types import MenuCommand

LABEL_TO_COMMAND: dict[str, MenuCommand] = {
    "Thumb_Up": MenuCommand.MOVE_UP,
    "Thumb_Down": MenuCommand.MOVE_DOWN,
    "Victory": MenuCommand.SELECT,
}

DEFAULT_MODEL = ASSETS / "models" / "gesture_recognizer.task"


@dataclass(frozen=True)
class HandGesture:
    """One recognised hand: its top gesture and where it is in the image."""

    label: str  # MediaPipe category, e.g. "Thumb_Up"
    score: float
    box: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax px

    @property
    def center(self) -> tuple[float, float]:
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)


@dataclass(frozen=True)
class GestureSnapshot:
    """Latest recognizer output for UI and position-based selection.

    `label`/`score`/`hand_box`/`landmarks` describe the single strongest hand
    (what the menu uses); `hands` lists every hand with a named gesture.
    """

    label: str | None
    score: float = 0.0
    hand_box: tuple[float, float, float, float] | None = None  # xmin, ymin, xmax, ymax px
    landmarks: tuple[tuple[float, float], ...] = ()  # image-pixel (x, y)
    hands: tuple[HandGesture, ...] = ()


@dataclass(frozen=True)
class GestureNavConfig:
    model_path: Path = DEFAULT_MODEL
    min_score: float = 0.5
    refractory_ms: int = 350


def load_gesture_nav_config() -> GestureNavConfig:
    """Env overrides for `MIN_SCORE` / `REFRACTORY_MS`; optional `GESTURE_MODEL_PATH`."""
    import os

    base = from_env(GestureNavConfig)
    gesture_model = os.environ.get("GESTURE_MODEL_PATH", "").strip()
    if not gesture_model:
        return base
    return GestureNavConfig(
        model_path=Path(gesture_model),
        min_score=base.min_score,
        refractory_ms=base.refractory_ms,
    )



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

    def __init__(self, config: GestureNavConfig | None = None, num_hands: int = 2) -> None:
        self.config = config or load_gesture_nav_config()
        self.num_hands = num_hands  # max hands tracked; change takes effect on start()
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
            num_hands=self.num_hands,
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

    def recognize(self, image_bgr: np.ndarray, timestamp_ms: int) -> GestureSnapshot:
        if not self._active or self._recognizer is None:
            return _empty_snapshot()

        import mediapipe as mp

        # VIDEO mode requires strictly increasing timestamps.
        if timestamp_ms <= self._last_ts_ms:
            timestamp_ms = self._last_ts_ms + 1
        self._last_ts_ms = timestamp_ms

        rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize_for_video(mp_image, timestamp_ms)

        h, w = image_bgr.shape[:2]
        landmarks = result.hand_landmarks or ()
        best_label: str | None = None
        best_score = 0.0
        best_index = -1
        hands: list[HandGesture] = []
        for i, hand_gestures in enumerate(result.gestures or ()):
            if not hand_gestures:
                continue
            top = hand_gestures[0]
            name = getattr(top, "category_name", None) or getattr(top, "display_name", None)
            score = float(top.score)
            if not name or name == "None":
                continue
            if i < len(landmarks):
                box, _ = _landmarks_to_box_and_pts(landmarks[i], w, h)
                hands.append(HandGesture(label=name, score=score, box=box))
            if score > best_score:
                best_score = score
                best_label = name
                best_index = i

        if best_index < 0 or best_index >= len(landmarks):
            return GestureSnapshot(label=best_label, score=best_score, hands=tuple(hands))

        box, pts = _landmarks_to_box_and_pts(landmarks[best_index], w, h)
        return GestureSnapshot(
            label=best_label, score=best_score, hand_box=box, landmarks=pts, hands=tuple(hands)
        )
