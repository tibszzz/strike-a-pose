"""Finding people and their joints in a camera frame.

Frames are expected already mirrored (see `camera.py`), so every coordinate
returned here is a screen coordinate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .pose import JOINT_NAMES, Point

# Left, top, right, bottom, in frame pixels.
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Person:
    joints: dict[str, Point]
    confidence: dict[str, float]
    box: Box

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    def visible_joints(self, min_confidence: float) -> dict[str, Point]:
        """Only the joints the model is confident it can see."""
        return {
            name: point
            for name, point in self.joints.items()
            if self.confidence[name] >= min_confidence
        }


def left_to_right(people: Sequence[Person]) -> list[Person]:
    return sorted(people, key=lambda person: person.center_x)


def select_players(people: Sequence[Person], count: int) -> list[Person] | None:
    """The `count` tallest people in frame, ordered left to right.

    Smaller figures are taken to be bystanders behind the players. Returns
    None when fewer than `count` people were found.
    """
    if len(people) < count:
        return None
    tallest = sorted(people, key=lambda person: person.height, reverse=True)[:count]
    return left_to_right(tallest)


class PoseDetector:
    def __init__(self, model_path: Path) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"pose model not found at {model_path}")
        # Imported here so the rest of the package, and its tests, load
        # without pulling in the model library.
        from ultralytics import YOLO

        self._model = YOLO(str(model_path))

    def detect(self, frame) -> list[Person]:
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
                Person(
                    joints={
                        name: (x, y) for name, (x, y) in zip(JOINT_NAMES, points)
                    },
                    confidence=dict(zip(JOINT_NAMES, confidences)),
                    box=(box[0], box[1], box[2], box[3]),
                )
            )
        return people
