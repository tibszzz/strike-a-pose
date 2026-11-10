import math

from builders import T_POSE

from strike_a_pose.games.strike.edit_fk import apply_drag, clip_translation, measure_lengths
from strike_a_pose.pose import HEAD_JOINT


def _dist(joints, a, b):
    return math.dist(joints[a], joints[b])


def _lengths(joints=None):
    return measure_lengths(joints or T_POSE)


def test_dragging_wrist_keeps_arm_bone_lengths():
    before = dict(T_POSE)
    lengths = _lengths(before)
    after = apply_drag(before, "left_wrist", (0.70, 0.45), lengths)
    assert after is not None
    assert math.isclose(_dist(after, "left_shoulder", "left_elbow"), lengths.left_upper, abs_tol=1e-9)
    assert math.isclose(_dist(after, "left_elbow", "left_wrist"), lengths.left_forearm, abs_tol=1e-9)
    assert after["left_shoulder"] == before["left_shoulder"]
    assert after["right_wrist"] == before["right_wrist"]


def test_dragging_wrist_beyond_reach_clamps_to_max_reach():
    before = dict(T_POSE)
    lengths = _lengths(before)
    after = apply_drag(before, "left_wrist", (1.0, 0.20), lengths)
    assert after is not None
    reach = _dist(after, "left_shoulder", "left_wrist")
    assert math.isclose(reach, lengths.left_upper + lengths.left_forearm, abs_tol=1e-9)


def test_dragging_elbow_leaves_torso_and_keeps_forearm_length():
    before = dict(T_POSE)
    lengths = _lengths(before)
    after = apply_drag(before, "left_elbow", (0.70, 0.35), lengths)
    assert after is not None
    assert after["left_elbow"] == (0.70, 0.35)
    assert after["left_shoulder"] == before["left_shoulder"]
    assert after["right_shoulder"] == before["right_shoulder"]
    assert after["left_hip"] == before["left_hip"]
    assert math.isclose(_dist(after, "left_elbow", "left_wrist"), lengths.left_forearm, abs_tol=1e-9)
    # Upper arm is unlocked from the torso while dragging the elbow.
    assert not math.isclose(
        _dist(after, "left_shoulder", "left_elbow"), lengths.left_upper, abs_tol=1e-9
    )


def test_dragging_shoulder_pins_limb_tips_in_world():
    before = dict(T_POSE)
    lengths = _lengths(before)
    left_wrist = before["left_wrist"]
    right_ankle = before["right_ankle"]
    after = apply_drag(before, "left_shoulder", (0.65, 0.22), lengths)
    assert after is not None
    assert after["left_shoulder"] == (0.65, 0.22)
    assert after["left_wrist"] == left_wrist or math.isclose(
        _dist(after, "left_shoulder", "left_wrist"),
        lengths.left_upper + lengths.left_forearm,
        abs_tol=1e-6,
    )
    # Prefer exact pin when still reachable after a small torso nudge.
    assert after["right_ankle"] == right_ankle
    assert math.isclose(_dist(after, "left_shoulder", "left_elbow"), lengths.left_upper, abs_tol=1e-9)


def test_dragging_nose_is_unconstrained():
    before = dict(T_POSE)
    lengths = _lengths(before)
    after = apply_drag(before, HEAD_JOINT, (0.55, 0.12), lengths)
    assert after is not None
    assert after[HEAD_JOINT] == (0.55, 0.12)
    assert after["left_wrist"] == before["left_wrist"]


def test_drag_that_would_leave_the_unit_square_is_refused():
    before = dict(T_POSE)
    lengths = _lengths(before)
    # Elbow near the right edge with wrist further right → tip leaves the panel.
    assert apply_drag(before, "left_elbow", (0.99, 0.20), lengths) is None


def test_translation_is_clipped_to_keep_every_joint_in_bounds():
    before = dict(T_POSE)
    after = clip_translation(before, 0.0, 1.0)
    assert max(y for _, y in after.values()) == 1.0
    hip_span = _dist(before, "left_hip", "right_hip")
    assert math.isclose(_dist(after, "left_hip", "right_hip"), hip_span, abs_tol=1e-9)
