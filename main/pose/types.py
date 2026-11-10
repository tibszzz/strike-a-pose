"""Plain data types for pose input. No heavy imports so games and tests stay light."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class KP:
    """COCO-17 keypoint indices, as produced by YOLO pose models."""

    NOSE = 0
    L_EYE, R_EYE, L_EAR, R_EAR = 1, 2, 3, 4
    L_SHOULDER, R_SHOULDER = 5, 6
    L_ELBOW, R_ELBOW = 7, 8
    L_WRIST, R_WRIST = 9, 10
    L_HIP, R_HIP = 11, 12
    L_KNEE, R_KNEE = 13, 14
    L_ANKLE, R_ANKLE = 15, 16


SKELETON = [
    (KP.L_SHOULDER, KP.R_SHOULDER),
    (KP.L_SHOULDER, KP.L_ELBOW), (KP.L_ELBOW, KP.L_WRIST),
    (KP.R_SHOULDER, KP.R_ELBOW), (KP.R_ELBOW, KP.R_WRIST),
    (KP.L_SHOULDER, KP.L_HIP), (KP.R_SHOULDER, KP.R_HIP), (KP.L_HIP, KP.R_HIP),
    (KP.L_HIP, KP.L_KNEE), (KP.L_KNEE, KP.L_ANKLE),
    (KP.R_HIP, KP.R_KNEE), (KP.R_KNEE, KP.R_ANKLE),
]


@dataclass(frozen=True)
class Person:
    xy: np.ndarray  # (17, 2) keypoint pixel coordinates in the (mirrored) frame
    conf: np.ndarray  # (17,) keypoint confidences
    box: tuple[float, float, float, float]  # x1, y1, x2, y2

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def area(self) -> float:
        return max(0.0, self.box[2] - self.box[0]) * max(0.0, self.box[3] - self.box[1])


Players = tuple["Person | None", "Person | None"]


@dataclass(frozen=True)
class PoseFrame:
    image: np.ndarray  # BGR camera image, already mirrored
    timestamp: float  # time.perf_counter() right after capture
    players: Players  # (left / P1, right / P2); None when not detected
    people: list[Person]  # all detections this frame, before 2-player assignment


def assign_players(people: list[Person], frame_width: float) -> Players:
    """Left half of the frame is P1, right half is P2.

    Keeps the two largest detections. With two people they are ordered by x; a lone
    person is placed by which half of the frame they stand in.
    """
    people = sorted(people, key=lambda p: p.area, reverse=True)[:2]
    if len(people) == 2:
        a, b = sorted(people, key=lambda p: p.center_x)
        return (a, b)
    if len(people) == 1:
        p = people[0]
        return (p, None) if p.center_x < frame_width / 2 else (None, p)
    return (None, None)
