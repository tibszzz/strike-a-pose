"""Camera plus pose model. Frames come back already mirrored.

This is the only place the image is flipped. Everything after it
(detection, scoring, drawing, saved poses) works in what the players
see on screen, which is what makes the game a mirror.
"""

from __future__ import annotations

from pathlib import Path

import cv2

from .types import JOINT_NAMES, Person


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, index: int) -> None:
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise CameraError(
                f"could not open camera {index}. Check that it is connected and "
                "that this terminal is allowed to use the camera."
            )

    def read(self):
        """One frame, flipped left to right."""
        ok, frame = self._capture.read()
        if not ok:
            raise CameraError("the camera stopped sending frames")
        return cv2.flip(frame, 1)

    def release(self) -> None:
        self._capture.release()


class PoseDetector:
    def __init__(self, model_path: Path) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"pose model not found at {model_path}")
        # Imported here so the rest of the package, and its tests, load
        # without pulling in the model library.
        from ultralytics import YOLO

        self._model = YOLO(str(model_path))

    def detect(self, frame) -> list[Person]:
        """Everyone the model finds in one frame, in no particular order.

        Frames are expected already mirrored (see `Camera`), so every
        coordinate returned here is a screen coordinate.
        """
        result = self._model(frame, verbose=False)[0]
        keypoints = result.keypoints
        if keypoints is None or keypoints.conf is None:
            return []

        people = []
        for points, confidences, box in zip(
            keypoints.xy.tolist(), keypoints.conf.tolist(), result.boxes.xyxy.tolist()
        ):
            people.append(
                Person(
                    joints={
                        name: (x, y) for name, (x, y) in zip(JOINT_NAMES, points)
                    },
                    confidence=dict(zip(JOINT_NAMES, confidences)),
                    box=(box[0], box[1], box[2], box[3]),
                )
            )
        return people
