import pytest
from builders import ONE_ARM_UP, T_POSE, person_striking

from main.games.strike.capture import is_valid_name, largest_person, pose_from_person
from main.games.strike.scoring import score_pose
from main.pose.library import PoseError, load_pose, save_pose

CONFIDENCE = 0.5


def test_captured_pose_matches_the_person_it_came_from():
    person = person_striking(ONE_ARM_UP, center_x=640.0, height=500.0)

    pose = pose_from_person("one-arm-up", person, CONFIDENCE)

    assert pose.name == "one-arm-up"
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pose.joints.values())
    # Coordinates are rounded to 3 places, so allow a hair under 100.
    assert score_pose(pose.joints, person.joints, 90.0) > 99.5


def test_captured_pose_is_exactly_what_gets_saved(tmp_path):
    pose = pose_from_person("one-arm-up", person_striking(ONE_ARM_UP, center_x=640.0), CONFIDENCE)
    path = tmp_path / "one-arm-up.json"
    save_pose(pose, path)
    assert load_pose(path) == pose


@pytest.mark.parametrize("hidden", ["left_ankle", "right_wrist", "left_hip"])
def test_capture_is_refused_when_a_body_joint_is_hidden(hidden):
    person = person_striking(T_POSE, center_x=640.0, hidden=(hidden,))
    with pytest.raises(PoseError, match=hidden):
        pose_from_person("t-pose", person, CONFIDENCE)


def test_hidden_nose_does_not_block_a_capture():
    person = person_striking(T_POSE, center_x=640.0, hidden=("nose",))
    assert "nose" not in pose_from_person("t-pose", person, CONFIDENCE).joints


def test_largest_person_is_the_tallest_in_frame():
    near = person_striking(T_POSE, center_x=900.0, height=500.0)
    far = person_striking(T_POSE, center_x=200.0, height=180.0)
    assert largest_person([far, near]) is near
    assert largest_person([]) is None


@pytest.mark.parametrize("name", ["arms-up", "t-pose", "pose2", "one-arm-up"])
def test_valid_pose_names(name):
    assert is_valid_name(name)


@pytest.mark.parametrize("name", ["", "Arms-Up", "arms up", "arms_up", "-arms", "arms-", "../x", "a.json"])
def test_invalid_pose_names(name):
    assert not is_valid_name(name)
