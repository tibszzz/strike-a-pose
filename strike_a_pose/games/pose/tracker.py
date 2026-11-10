"""Camera + YOLO pose inference, producing one PoseFrame per call."""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

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
