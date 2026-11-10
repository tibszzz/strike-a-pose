import json

import pytest
from builders import ONE_ARM_UP, T_POSE

from strike_a_pose.config import Config
from strike_a_pose.pose import (
    BODY_JOINTS,
    Pose,
    PoseError,
    load_library,
    load_pose,
    normalize_joints,
    pose_from_dict,
    save_pose,
)
from strike_a_pose.scoring import score_pose


def as_file_data(joints, name="test-pose"):
    return {"name": name, "joints": {joint: list(point) for joint, point in joints.items()}}


# --- the starter library ---------------------------------------------------


def test_every_starter_pose_loads_with_all_body_joints():
    library = load_library(Config().poses_dir)
    assert library, "no pose files found"
    for pose in library:
        assert set(BODY_JOINTS) <= set(pose.joints), pose.name


def test_starter_library_has_enough_poses_for_a_game():
    config = Config()
    assert len(load_library(config.poses_dir)) >= config.rounds


def test_starter_pose_names_match_their_file_names():
    for path in sorted(Config().poses_dir.glob("*.json")):
        assert load_pose(path).name == path.stem


# --- validation ------------------------------------------------------------


def test_valid_pose_is_accepted():
    pose = pose_from_dict(as_file_data(ONE_ARM_UP))
    assert pose.name == "test-pose"
    assert pose.joints["right_wrist"] == (0.32, 0.0)


def test_nose_is_optional():
    without_nose = {name: point for name, point in T_POSE.items() if name != "nose"}
    assert "nose" not in pose_from_dict(as_file_data(without_nose)).joints


@pytest.mark.parametrize("joint", BODY_JOINTS)
def test_pose_missing_a_body_joint_is_rejected(joint):
    incomplete = {name: point for name, point in T_POSE.items() if name != joint}
    with pytest.raises(PoseError, match=joint):
        pose_from_dict(as_file_data(incomplete))


def test_misspelled_joint_is_rejected_by_name():
    data = as_file_data(T_POSE)
    data["joints"]["left_sholder"] = [0.6, 0.2]
    with pytest.raises(PoseError, match="left_sholder"):
        pose_from_dict(data)


@pytest.mark.parametrize(
    "bad_value",
    [[1.5, 0.2], [-0.1, 0.2], [0.5], [0.5, 0.2, 0.1], ["0.5", 0.2], [True, 0.2], 0.5, None],
)
def test_bad_coordinates_are_rejected(bad_value):
    data = as_file_data(T_POSE)
    data["joints"]["left_wrist"] = bad_value
    with pytest.raises(PoseError, match="left_wrist"):
        pose_from_dict(data)


def test_segment_with_no_length_is_rejected():
    data = as_file_data(T_POSE)
    data["joints"]["left_wrist"] = data["joints"]["left_elbow"]
    with pytest.raises(PoseError, match="left_forearm"):
        pose_from_dict(data)


@pytest.mark.parametrize("bad_name", [None, "", "   ", 7])
def test_pose_without_a_name_is_rejected(bad_name):
    with pytest.raises(PoseError, match="name"):
        pose_from_dict(as_file_data(T_POSE, name=bad_name))


# --- files -----------------------------------------------------------------


def test_saved_pose_loads_back_the_same(tmp_path):
    path = tmp_path / "one-arm-up.json"
    save_pose(Pose(name="one-arm-up", joints=dict(ONE_ARM_UP)), path)
    loaded = load_pose(path)
    assert loaded.name == "one-arm-up"
    assert loaded.joints == ONE_ARM_UP


def test_load_error_names_the_file(tmp_path):
    path = tmp_path / "broken.json"
    data = as_file_data(T_POSE)
    del data["joints"]["left_knee"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PoseError, match="broken.json"):
        load_pose(path)


def test_file_that_is_not_json_is_rejected(tmp_path):
    path = tmp_path / "not-json.json"
    path.write_text("{ nope", encoding="utf-8")
    with pytest.raises(PoseError, match="not valid JSON"):
        load_pose(path)


# --- normalizing a captured pose -------------------------------------------


def test_normalized_joints_fit_the_unit_box_and_keep_their_directions():
    in_camera_pixels = {
        name: (x * 300 + 640, y * 300 + 200) for name, (x, y) in ONE_ARM_UP.items()
    }
    normalized = normalize_joints(in_camera_pixels)

    xs = [x for x, _ in normalized.values()]
    ys = [y for _, y in normalized.values()]
    assert min(xs) >= 0 and max(xs) <= 1
    assert min(ys) == pytest.approx(0) and max(ys) == pytest.approx(1)
    assert score_pose(ONE_ARM_UP, normalized, 90.0) == pytest.approx(100.0)
