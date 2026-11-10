"""Camera + YOLO. Two front ends share this module.

`PoseTracker` returns a `PoseFrame` for pygame games (duel).
`Camera` + `PoseDetector` feed the OpenCV strike game with named joints.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from . import library
from .types import Person, PoseFrame, assign_players

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = REPO_ROOT / "assets" / "models" / "yolo26n-pose.pt"


def default_device() -> str:
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class PoseTracker:
    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        imgsz: int = 640,
        device: str | None = None,
        mirror: bool = True,
    ) -> None:
        from ultralytics import YOLO  # heavy import, keep it out of module import time

        self.device = device or default_device()
        self.imgsz = imgsz
        self.mirror = mirror
        self.model = YOLO(str(model_path))
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera {camera_index}. On macOS, allow camera access "
                "for your terminal/editor in System Settings > Privacy & Security > Camera."
            )

    def read(self) -> PoseFrame:
        ok, image = self.cap.read()
        timestamp = time.perf_counter()
        if not ok:
            raise RuntimeError("Camera stopped delivering frames.")
        if self.mirror:
            image = cv2.flip(image, 1)

        result = self.model(image, device=self.device, imgsz=self.imgsz, verbose=False)[0]
        people: list[Person] = []
        if result.keypoints is not None and result.boxes is not None and len(result.boxes):
            xy = result.keypoints.xy.cpu().numpy()
            kconf = result.keypoints.conf
            conf = kconf.cpu().numpy() if kconf is not None else np.ones(xy.shape[:2])
            boxes = result.boxes.xyxy.cpu().numpy()
            for i in range(len(boxes)):
                people.append(Person(xy=xy[i], conf=conf[i], box=tuple(map(float, boxes[i]))))

        return PoseFrame(image, timestamp, assign_players(people, image.shape[1]))

    def close(self) -> None:
        self.cap.release()


class CameraError(RuntimeError):
    pass


class Camera:
    """Webcam reader for the strike game. Frames come back already mirrored."""

    def __init__(self, index: int) -> None:
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise CameraError(
                f"could not open camera {index}. Check that it is connected and "
                "that this terminal is allowed to use the camera."
            )

    def read(self):
        """One frame, flipped left to right.

        This is the only place the image is flipped for the strike game.
        Everything after it works in what the players see on screen.
        """
        ok, frame = self._capture.read()
        if not ok:
            raise CameraError("the camera stopped sending frames")
        return cv2.flip(frame, 1)

    def release(self) -> None:
        self._capture.release()


class PoseDetector:
    """Named-joint detector for the strike game."""

    def __init__(self, model_path: Path) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"pose model not found at {model_path}")
        # Imported here so the rest of the package, and its tests, load
        # without pulling in the model library.
        from ultralytics import YOLO

        self._model = YOLO(str(model_path))

    def detect(self, frame) -> list[library.Person]:
        """Everyone the model finds in one frame, in no particular order."""
        result = self._model(frame, verbose=False)[0]
        keypoints = result.keypoints
        if keypoints is None or keypoints.conf is None:
            return []

        people = []
        for points, confidences, box in zip(
            keypoints.xy.tolist(), keypoints.conf.tolist(), result.boxes.xyxy.tolist()
        ):
            people.append(
                library.Person(
                    joints={
                        name: (x, y) for name, (x, y) in zip(library.JOINT_NAMES, points)
                    },
                    confidence=dict(zip(library.JOINT_NAMES, confidences)),
                    box=(box[0], box[1], box[2], box[3]),
                )
            )
        return people
