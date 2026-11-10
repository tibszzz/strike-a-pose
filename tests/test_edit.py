import math
from pathlib import Path

from builders import T_POSE

from strike_a_pose.edit import PoseEditor, nearest_joint
from strike_a_pose.edit_fk import apply_drag
from strike_a_pose.pose import HEAD_JOINT, Pose, save_pose


def _nudge(editor):
    moved = apply_drag(
        editor.joints, "left_wrist", (0.70, 0.40), editor.lengths
    )
    assert moved is not None
    editor.joints = moved
    return editor


def _seed(tmp_path: Path) -> Path:
    path = tmp_path / "t-pose.json"
    save_pose(Pose(name="t-pose", joints=dict(T_POSE)), path)
    return path


def test_create_opens_from_t_pose_seed(tmp_path):
    seed = _seed(tmp_path)
    target = tmp_path / "wave.json"
    editor = PoseEditor.open("wave", target, seed)
    assert editor.existed_at_open is False
    assert editor.joints == dict(T_POSE)
    assert editor.name == "wave"
    assert not editor.dirty


def test_edit_loads_existing_pose(tmp_path):
    seed = _seed(tmp_path)
    path = tmp_path / "wave.json"
    joints = {**T_POSE, "left_wrist": (0.80, 0.10)}
    save_pose(Pose(name="wave", joints=joints), path)
    editor = PoseEditor.open("wave", path, seed)
    assert editor.existed_at_open is True
    assert editor.joints["left_wrist"] == (0.80, 0.10)


def test_new_pose_saves_without_confirm(tmp_path):
    seed = _seed(tmp_path)
    path = tmp_path / "wave.json"
    editor = PoseEditor.open("wave", path, seed)
    _nudge(editor)
    assert editor.dirty
    editor.confirm()
    assert path.exists()
    assert not editor.dirty
    assert editor.status.startswith("Saved")


def test_existing_pose_requires_overwrite_confirm(tmp_path):
    seed = _seed(tmp_path)
    path = tmp_path / "wave.json"
    save_pose(Pose(name="wave", joints=dict(T_POSE)), path)
    original = path.read_text()
    editor = PoseEditor.open("wave", path, seed)
    _nudge(editor)
    editor.confirm()
    assert editor.phase.name == "CONFIRM_OVERWRITE"
    assert path.read_text() == original
    editor.confirm()
    assert path.read_text() != original
    assert not editor.dirty


def test_quit_asks_before_discarding_dirty_state(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    _nudge(editor)
    assert editor.request_quit() is False
    assert editor.phase.name == "CONFIRM_DISCARD"
    assert editor.request_quit() is True


def test_quit_clean_exits_immediately(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    assert editor.request_quit() is True


def test_reset_restores_open_joints(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    _nudge(editor)
    editor.reset()
    assert editor.joints == dict(T_POSE)


def test_capture_refreezes_bone_lengths(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    open_upper = editor.lengths.left_upper
    stretched = {
        **T_POSE,
        "left_elbow": (0.80, 0.20),
        "left_wrist": (1.00, 0.20),
    }
    editor.apply_capture(Pose(name="wave", joints=stretched))
    assert editor.lengths.left_upper != open_upper
    assert editor.lengths.left_upper == math.dist(
        stretched["left_shoulder"], stretched["left_elbow"]
    )
    editor.reset()
    assert editor.lengths.left_upper == open_upper


def test_nose_toggle_uses_seed_offset(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    assert HEAD_JOINT in editor.joints
    editor.toggle_nose()
    assert HEAD_JOINT not in editor.joints
    editor.toggle_nose()
    assert HEAD_JOINT in editor.joints
    mid_x = (editor.joints["left_shoulder"][0] + editor.joints["right_shoulder"][0]) / 2
    mid_y = (editor.joints["left_shoulder"][1] + editor.joints["right_shoulder"][1]) / 2
    assert editor.joints[HEAD_JOINT] == (
        mid_x + (T_POSE[HEAD_JOINT][0] - (T_POSE["left_shoulder"][0] + T_POSE["right_shoulder"][0]) / 2),
        mid_y + (T_POSE[HEAD_JOINT][1] - (T_POSE["left_shoulder"][1] + T_POSE["right_shoulder"][1]) / 2),
    )


def test_nearest_joint_picks_the_closest_within_radius():
    joints = {"a": (0.0, 0.0), "b": (0.1, 0.0)}
    assert nearest_joint(joints, (0.02, 0.0), 0.05) == "a"
    assert nearest_joint(joints, (0.5, 0.5), 0.05) is None


def test_camera_capture_loads_joints_without_saving(tmp_path):
    seed = _seed(tmp_path)
    path = tmp_path / "wave.json"
    editor = PoseEditor.open("wave", path, seed)
    editor.start_capture()
    assert editor.phase.name == "CAPTURING"

    snapped = Pose(name="wave", joints={**T_POSE, "left_wrist": (0.80, 0.05)})
    editor.apply_capture(snapped)

    assert editor.phase.name == "EDITING"
    assert editor.joints["left_wrist"] == (0.80, 0.05)
    assert editor.dirty
    assert not path.exists()
    assert editor.status.startswith("Captured")


def test_quit_during_capture_returns_to_editor(tmp_path):
    seed = _seed(tmp_path)
    editor = PoseEditor.open("wave", tmp_path / "wave.json", seed)
    before = dict(editor.joints)
    editor.start_capture()
    assert editor.request_quit() is False
    assert editor.phase.name == "EDITING"
    assert editor.joints == before
