"""How close a player's pose is to a target, as a score from 0 to 100.

Each of the 9 segments is compared by the direction it points on screen, so a
player's height, distance from the camera and position in frame do not
matter. Every segment carries the same weight.
"""

from __future__ import annotations

import math

from strike_a_pose.pose import SEGMENTS, Joints, Point, segment_vector


def angle_between(a: Point, b: Point) -> float:
    """Angle between two directions, in degrees from 0 to 180."""
    dot = a[0] * b[0] + a[1] * b[1]
    cross = a[0] * b[1] - a[1] * b[0]
    return math.degrees(math.atan2(abs(cross), dot))


def segment_score(angle_degrees: float, strictness_degrees: float) -> float:
    """100 at 0 degrees off, falling in a straight line to 0 at the strictness."""
    return max(0.0, 1.0 - angle_degrees / strictness_degrees) * 100.0


def score_pose(target: Joints, player: Joints, strictness_degrees: float) -> float:
    """Average segment score, unrounded.

    `player` holds only the joints the camera could see. A segment with a
    hidden joint scores 0, and so does one with no length on screen, because
    it has no direction to compare.
    """
    total = 0.0
    for segment in SEGMENTS:
        target_vector = segment_vector(target, segment)
        if target_vector is None or math.hypot(*target_vector) == 0:
            raise ValueError(f"target pose has no direction for {segment}")
        player_vector = segment_vector(player, segment)
        if player_vector is None or math.hypot(*player_vector) == 0:
            continue
        angle = angle_between(target_vector, player_vector)
        total += segment_score(angle, strictness_degrees)
    return total / len(SEGMENTS)


def round_score(score: float) -> int:
    """Round to a whole number, with halves going up."""
    return math.floor(score + 0.5)
