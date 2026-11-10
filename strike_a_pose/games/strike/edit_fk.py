"""Pose-editor drags: free cursor on the grabbed joint, live bone-length solve.

Limb tips use 2-bone IK from a pinned root. Middles free-drag without moving
the torso; only the outer bone length (to the tip) is kept. Torso grabs
translate the rigid box while limb tips stay world-pinned. Nose is unconstrained.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from strike_a_pose.pose import HEAD_JOINT, Joints, Point, midpoint

TORSO_JOINTS = frozenset(
    {"left_shoulder", "right_shoulder", "left_hip", "right_hip"}
)

# tip -> (root, middle, upper_length attr, lower_length attr)
_LIMBS: dict[str, tuple[str, str, str, str]] = {
    "left_wrist": ("left_shoulder", "left_elbow", "left_upper", "left_forearm"),
    "right_wrist": ("right_shoulder", "right_elbow", "right_upper", "right_forearm"),
    "left_ankle": ("left_hip", "left_knee", "left_thigh", "left_shin"),
    "right_ankle": ("right_hip", "right_knee", "right_thigh", "right_shin"),
}

# middle -> (root, tip, upper attr, lower attr)
_MIDDLES: dict[str, tuple[str, str, str, str]] = {
    "left_elbow": ("left_shoulder", "left_wrist", "left_upper", "left_forearm"),
    "right_elbow": ("right_shoulder", "right_wrist", "right_upper", "right_forearm"),
    "left_knee": ("left_hip", "left_ankle", "left_thigh", "left_shin"),
    "right_knee": ("right_hip", "right_ankle", "right_thigh", "right_shin"),
}


@dataclass(frozen=True)
class BoneLengths:
    left_upper: float
    left_forearm: float
    right_upper: float
    right_forearm: float
    left_thigh: float
    left_shin: float
    right_thigh: float
    right_shin: float

    def get(self, name: str) -> float:
        return getattr(self, name)


def mid_shoulder(joints: Joints) -> Point:
    point = midpoint(joints, ("left_shoulder", "right_shoulder"))
    assert point is not None
    return point


def measure_lengths(joints: Joints) -> BoneLengths:
    return BoneLengths(
        left_upper=_dist(joints, "left_shoulder", "left_elbow"),
        left_forearm=_dist(joints, "left_elbow", "left_wrist"),
        right_upper=_dist(joints, "right_shoulder", "right_elbow"),
        right_forearm=_dist(joints, "right_elbow", "right_wrist"),
        left_thigh=_dist(joints, "left_hip", "left_knee"),
        left_shin=_dist(joints, "left_knee", "left_ankle"),
        right_thigh=_dist(joints, "right_hip", "right_knee"),
        right_shin=_dist(joints, "right_knee", "right_ankle"),
    )


def _dist(joints: Joints, a: str, b: str) -> float:
    return math.dist(joints[a], joints[b])


def _clamp_unit(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _clamp_point(point: Point) -> Point:
    return (_clamp_unit(point[0]), _clamp_unit(point[1]))


def in_unit_square(joints: Joints) -> bool:
    return all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in joints.values())


def _normalize(dx: float, dy: float) -> Point | None:
    length = math.hypot(dx, dy)
    if length == 0:
        return None
    return (dx / length, dy / length)


def _add(point: Point, dx: float, dy: float) -> Point:
    return (point[0] + dx, point[1] + dy)


def _scale(vec: Point, scalar: float) -> Point:
    return (vec[0] * scalar, vec[1] * scalar)


def clip_translation(joints: Joints, dx: float, dy: float) -> dict[str, Point]:
    """Translate every joint, shrinking the delta so all stay in [0, 1]."""
    xs = [point[0] for point in joints.values()]
    ys = [point[1] for point in joints.values()]
    dx = min(max(dx, -min(xs)), 1.0 - max(xs))
    dy = min(max(dy, -min(ys)), 1.0 - max(ys))
    return {name: (point[0] + dx, point[1] + dy) for name, point in joints.items()}


def _clamp_reach(root: Point, target: Point, upper: float, lower: float) -> Point:
    direction = _normalize(target[0] - root[0], target[1] - root[1])
    if direction is None:
        direction = (1.0, 0.0)
    distance = math.dist(root, target)
    max_reach = upper + lower
    min_reach = abs(upper - lower)
    if distance > max_reach:
        return _add(root, *_scale(direction, max_reach))
    if distance < min_reach:
        return _add(root, *_scale(direction, min_reach))
    return target


def _solve_middle(
    root: Point, tip: Point, upper: float, lower: float, previous: Point
) -> Point:
    """2-bone IK: place the middle joint; pick the solution nearer `previous`."""
    tip = _clamp_reach(root, tip, upper, lower)
    offset = _normalize(tip[0] - root[0], tip[1] - root[1])
    if offset is None:
        offset = (1.0, 0.0)
    distance = math.dist(root, tip)
    # Law of cosines: angle between root→tip and root→middle.
    cos_angle = (upper * upper + distance * distance - lower * lower) / (
        2.0 * upper * max(distance, 1e-9)
    )
    cos_angle = min(max(cos_angle, -1.0), 1.0)
    angle = math.acos(cos_angle)
    ox, oy = offset
    # Two perpendicular rotations of the root→tip direction.
    candidates = []
    for sign in (1.0, -1.0):
        rotated = (
            ox * math.cos(sign * angle) - oy * math.sin(sign * angle),
            ox * math.sin(sign * angle) + oy * math.cos(sign * angle),
        )
        candidates.append(_add(root, *_scale(rotated, upper)))
    return min(candidates, key=lambda point: math.dist(point, previous))


def _translate_torso(joints: dict[str, Point], dx: float, dy: float) -> None:
    for name in TORSO_JOINTS:
        x, y = joints[name]
        joints[name] = (x + dx, y + dy)


def _resettle_limbs(
    joints: dict[str, Point],
    lengths: BoneLengths,
    pinned_tips: dict[str, Point],
    previous: Joints,
) -> None:
    """IK each limb toward a world-pinned tip from the (possibly moved) root."""
    for tip_name, (root_name, middle_name, upper_attr, lower_attr) in _LIMBS.items():
        tip = pinned_tips[tip_name]
        root = joints[root_name]
        tip = _clamp_reach(
            root, tip, lengths.get(upper_attr), lengths.get(lower_attr)
        )
        joints[tip_name] = tip
        joints[middle_name] = _solve_middle(
            root,
            tip,
            lengths.get(upper_attr),
            lengths.get(lower_attr),
            previous[middle_name],
        )


def _drag_tip(
    joints: Joints, tip_name: str, target: Point, lengths: BoneLengths
) -> dict[str, Point] | None:
    root_name, middle_name, upper_attr, lower_attr = _LIMBS[tip_name]
    proposed = dict(joints)
    root = proposed[root_name]
    tip = _clamp_reach(
        root, target, lengths.get(upper_attr), lengths.get(lower_attr)
    )
    proposed[tip_name] = tip
    proposed[middle_name] = _solve_middle(
        root,
        tip,
        lengths.get(upper_attr),
        lengths.get(lower_attr),
        joints[middle_name],
    )
    if not in_unit_square(proposed):
        return None
    return proposed


def _drag_middle(
    joints: Joints, middle_name: str, target: Point, lengths: BoneLengths
) -> dict[str, Point] | None:
    """Place the middle at the cursor; torso stays put; tip keeps outer length."""
    _root_name, tip_name, _upper_attr, lower_attr = _MIDDLES[middle_name]
    old_mid = joints[middle_name]
    lower = lengths.get(lower_attr)
    tip_dir = _normalize(
        joints[tip_name][0] - old_mid[0], joints[tip_name][1] - old_mid[1]
    )
    if tip_dir is None:
        tip_dir = (1.0, 0.0)

    proposed = dict(joints)
    proposed[middle_name] = target
    proposed[tip_name] = _add(target, *_scale(tip_dir, lower))
    if not in_unit_square(proposed):
        return None
    return proposed


def _drag_torso(
    joints: Joints, joint: str, target: Point, lengths: BoneLengths
) -> dict[str, Point] | None:
    dx = target[0] - joints[joint][0]
    dy = target[1] - joints[joint][1]
    proposed = dict(joints)
    _translate_torso(proposed, dx, dy)
    pinned = {name: joints[name] for name in _LIMBS}
    _resettle_limbs(proposed, lengths, pinned, joints)
    if not in_unit_square(proposed):
        return None
    return proposed


def apply_drag(
    joints: Joints, joint: str, cursor: Point, lengths: BoneLengths
) -> dict[str, Point] | None:
    """Move `joint` toward `cursor` with live length constraints.

    Returns None when the solved pose would leave the unit square.
    """
    if joint not in joints:
        return None
    target = _clamp_point(cursor)

    if joint == HEAD_JOINT:
        proposed = {**dict(joints), HEAD_JOINT: target}
        return proposed if in_unit_square(proposed) else None

    if joint in _LIMBS:
        return _drag_tip(joints, joint, target, lengths)

    if joint in _MIDDLES:
        return _drag_middle(joints, joint, target, lengths)

    if joint in TORSO_JOINTS:
        return _drag_torso(joints, joint, target, lengths)

    return None
