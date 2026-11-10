"""Shared test data and helpers."""

from __future__ import annotations

import math

from main.pose import Person
from main.pose import Joints, Point

# Arms straight out to the sides, legs straight down. Left-right symmetric.
T_POSE: dict[str, Point] = {
    "nose": (0.50, 0.06),
    "left_shoulder": (0.60, 0.20),
    "right_shoulder": (0.40, 0.20),
    "left_elbow": (0.74, 0.20),
    "right_elbow": (0.26, 0.20),
    "left_wrist": (0.88, 0.20),
    "right_wrist": (0.12, 0.20),
    "left_hip": (0.56, 0.50),
    "right_hip": (0.44, 0.50),
    "left_knee": (0.56, 0.72),
    "right_knee": (0.44, 0.72),
    "left_ankle": (0.56, 0.94),
    "right_ankle": (0.44, 0.94),
}

# The T-pose with the arm on the left of the screen raised instead.
ONE_ARM_UP: dict[str, Point] = {
    **T_POSE,
    "right_elbow": (0.36, 0.10),
    "right_wrist": (0.32, 0.00),
}


def mirrored(joints: Joints) -> dict[str, Point]:
    """What the camera sees when a player copies a pose the wrong way round.

    The figure is flipped left to right, and because the model names joints
    by how the body looks, left and right names swap with it.
    """
    swap = {"left": "right", "right": "left"}
    flipped: dict[str, Point] = {}
    for name, (x, y) in joints.items():
        side, _, rest = name.partition("_")
        new_name = f"{swap[side]}_{rest}" if side in swap else name
        flipped[new_name] = (1.0 - x, y)
    return flipped


def with_joint_rotated(
    joints: Joints, joint: str, pivot: str, degrees: float
) -> dict[str, Point]:
    """Copy of the joints with one joint swung around another."""
    px, py = joints[pivot]
    dx, dy = joints[joint][0] - px, joints[joint][1] - py
    angle = math.radians(degrees)
    rotated = (
        px + dx * math.cos(angle) - dy * math.sin(angle),
        py + dx * math.sin(angle) + dy * math.cos(angle),
    )
    return {**joints, joint: rotated}


def person_striking(
    joints: Joints,
    center_x: float,
    height: float = 400.0,
    top: float = 100.0,
    hidden: tuple[str, ...] = (),
) -> Person:
    """A detected person holding the given pose somewhere in a camera frame.

    Joints named in `hidden` are reported with low confidence, the way the
    model reports a joint it cannot see.
    """
    placed = {
        name: (center_x + (x - 0.5) * height, top + y * height)
        for name, (x, y) in joints.items()
    }
    confidence = {name: (0.1 if name in hidden else 0.95) for name in placed}
    box = (center_x - height / 2, top, center_x + height / 2, top + height)
    return Person(joints=placed, confidence=confidence, box=box)
