"""Pose data: joint names, the scored segments, and pose files.

All coordinates are screen coordinates: x grows to the right, y grows
downward, as the figure appears to someone looking at the screen. Joint names
follow the figure's own left and right as it faces the viewer, so a
`left_*` joint normally sits on the right side of the screen.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

Point = tuple[float, float]
Joints = Mapping[str, Point]

# The 17 keypoints the pose model reports, in the model's order.
JOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

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


HEAD_JOINT = "nose"
BODY_JOINTS = JOINT_NAMES[5:]
POSE_FILE_JOINTS = (HEAD_JOINT, *BODY_JOINTS)

# Each scored segment runs from one point to another. A point is the average
# of the joints listed for it, which is how the torso gets its two midpoints.
SEGMENTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "left_upper_arm": (("left_shoulder",), ("left_elbow",)),
    "left_forearm": (("left_elbow",), ("left_wrist",)),
    "right_upper_arm": (("right_shoulder",), ("right_elbow",)),
    "right_forearm": (("right_elbow",), ("right_wrist",)),
    "left_thigh": (("left_hip",), ("left_knee",)),
    "left_shin": (("left_knee",), ("left_ankle",)),
    "right_thigh": (("right_hip",), ("right_knee",)),
    "right_shin": (("right_knee",), ("right_ankle",)),
    "torso": (("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")),
}

# Joint pairs to connect when drawing a skeleton.
BONES = (
    ("left_shoulder", "right_shoulder"),
    ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
)


class PoseError(ValueError):
    """A pose is missing something it needs or holds a bad value."""


@dataclass(frozen=True)
class Pose:
    name: str
    joints: dict[str, Point]


def midpoint(joints: Joints, names: tuple[str, ...]) -> Point | None:
    """Average position of the named joints, or None if any is absent."""
    if any(name not in joints for name in names):
        return None
    xs = [joints[name][0] for name in names]
    ys = [joints[name][1] for name in names]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def segment_vector(joints: Joints, segment: str) -> Point | None:
    """Vector along a segment, or None if one of its joints is absent."""
    start_names, end_names = SEGMENTS[segment]
    start = midpoint(joints, start_names)
    end = midpoint(joints, end_names)
    if start is None or end is None:
        return None
    return (end[0] - start[0], end[1] - start[1])


def normalize_joints(joints: Joints) -> dict[str, Point]:
    """Scale and shift joints so the figure fits, centred, in a 0-1 box.

    Both axes are scaled by the same amount, so every segment keeps its
    direction.
    """
    xs = [point[0] for point in joints.values()]
    ys = [point[1] for point in joints.values()]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    extent = max(width, height)
    if extent == 0:
        raise PoseError("cannot normalize joints that all sit on one point")
    x_offset = (1 - width / extent) / 2
    y_offset = (1 - height / extent) / 2
    return {
        name: (
            (point[0] - min(xs)) / extent + x_offset,
            (point[1] - min(ys)) / extent + y_offset,
        )
        for name, point in joints.items()
    }


def pose_from_dict(data: object) -> Pose:
    """Build a pose from parsed JSON, rejecting anything the game cannot score."""
    if not isinstance(data, dict):
        raise PoseError("a pose must be a JSON object")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PoseError('a pose needs a non-empty "name"')

    raw_joints = data.get("joints")
    if not isinstance(raw_joints, dict):
        raise PoseError(f'pose "{name}" needs a "joints" object')

    unknown = sorted(set(raw_joints) - set(POSE_FILE_JOINTS))
    if unknown:
        raise PoseError(f'pose "{name}" has unknown joints: {", ".join(unknown)}')

    missing = [joint for joint in BODY_JOINTS if joint not in raw_joints]
    if missing:
        raise PoseError(f'pose "{name}" is missing joints: {", ".join(missing)}')

    joints: dict[str, Point] = {}
    for joint, value in raw_joints.items():
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or not all(_is_coordinate(number) for number in value)
        ):
            raise PoseError(
                f'pose "{name}": {joint} must be [x, y] with both between 0 and 1'
            )
        joints[joint] = (float(value[0]), float(value[1]))

    for segment in SEGMENTS:
        vector = segment_vector(joints, segment)
        if vector is None or math.hypot(*vector) == 0:
            raise PoseError(
                f'pose "{name}": {segment} has no length, so it has no direction'
            )

    return Pose(name=name, joints=joints)


def _is_coordinate(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0 <= value <= 1


def load_pose(path: Path) -> Pose:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PoseError(f"{path} is not valid JSON: {error}") from error
    try:
        return pose_from_dict(data)
    except PoseError as error:
        raise PoseError(f"{path}: {error}") from error


def load_library(directory: Path) -> list[Pose]:
    """Load every pose file in a folder, in file-name order."""
    return [load_pose(path) for path in sorted(directory.glob("*.json"))]


def save_pose(pose: Pose, path: Path) -> None:
    """Write a pose file: one joint per line, fixed order, 3 decimal places.

    Laid out by hand rather than with `json.dumps(indent=...)`, which would
    spread each [x, y] pair over four lines and make files hard to edit.
    """
    joint_lines = [
        f'    "{joint}": [{pose.joints[joint][0]:.3f}, {pose.joints[joint][1]:.3f}]'
        for joint in POSE_FILE_JOINTS
        if joint in pose.joints
    ]
    text = (
        "{\n"
        f'  "name": {json.dumps(pose.name)},\n'
        '  "joints": {\n' + ",\n".join(joint_lines) + "\n"
        "  }\n"
        "}\n"
    )
    path.write_text(text, encoding="utf-8")
