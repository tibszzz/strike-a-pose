import pytest
from builders import ONE_ARM_UP, T_POSE, mirrored, with_joint_rotated

from strike_a_pose.games.strike.scoring import round_score, score_pose, segment_score

STRICTNESS = 90.0


def test_identical_pose_scores_100():
    assert score_pose(ONE_ARM_UP, ONE_ARM_UP, STRICTNESS) == 100.0


def test_size_and_position_do_not_matter():
    far_right_and_large = {
        name: (x * 340 + 500, y * 340 + 120) for name, (x, y) in ONE_ARM_UP.items()
    }
    assert score_pose(ONE_ARM_UP, far_right_and_large, STRICTNESS) == pytest.approx(100.0)


def test_copying_an_asymmetric_pose_the_wrong_way_round_scores_lower():
    assert score_pose(ONE_ARM_UP, mirrored(ONE_ARM_UP), STRICTNESS) < 100.0


def test_mirror_image_of_a_symmetric_pose_still_scores_100():
    assert score_pose(T_POSE, mirrored(T_POSE), STRICTNESS) == pytest.approx(100.0)


def test_segment_45_degrees_off_scores_50():
    assert segment_score(45.0, STRICTNESS) == 50.0


def test_one_segment_45_degrees_off_costs_half_of_that_segment():
    player = with_joint_rotated(T_POSE, "left_wrist", "left_elbow", 45.0)
    assert score_pose(T_POSE, player, STRICTNESS) == pytest.approx((8 * 100 + 50) / 9)


@pytest.mark.parametrize("angle", [90.0, 135.0, 180.0])
def test_segment_at_or_past_the_strictness_angle_scores_0(angle):
    assert segment_score(angle, STRICTNESS) == 0.0


def test_lower_strictness_is_harsher():
    player = with_joint_rotated(T_POSE, "left_wrist", "left_elbow", 45.0)
    assert score_pose(T_POSE, player, 45.0) == pytest.approx(8 * 100 / 9)


@pytest.mark.parametrize(
    ("hidden_joint", "segments_lost"),
    [
        ("left_wrist", 1),  # forearm
        ("left_elbow", 2),  # upper arm and forearm
        ("left_shoulder", 2),  # upper arm and torso
        ("right_ankle", 1),  # shin
        ("nose", 0),  # the head is not scored
    ],
)
def test_hidden_joint_zeroes_every_segment_it_belongs_to(hidden_joint, segments_lost):
    player = {name: point for name, point in T_POSE.items() if name != hidden_joint}
    expected = (9 - segments_lost) * 100 / 9
    assert score_pose(T_POSE, player, STRICTNESS) == pytest.approx(expected)


def test_segment_with_no_length_on_screen_scores_0():
    arm_pointing_at_camera = {**T_POSE, "left_wrist": T_POSE["left_elbow"]}
    assert score_pose(T_POSE, arm_pointing_at_camera, STRICTNESS) == pytest.approx(
        8 * 100 / 9
    )


def test_nobody_visible_scores_0():
    assert score_pose(T_POSE, {}, STRICTNESS) == 0.0


@pytest.mark.parametrize(
    ("score", "rounded"),
    [(100.0, 100), (88.49, 88), (88.5, 89), (0.5, 1), (0.0, 0)],
)
def test_round_score_rounds_halves_up(score, rounded):
    assert round_score(score) == rounded
