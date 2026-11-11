"""Pose game module - contains pose detection, rendering, and screen management."""

# Import submodules but don't import everything at once to avoid dependency issues
# Users should import directly from the submodules they need

# Make the submodules available (lazy loading to avoid cv2 dependency)
__all__ = [
    'BONES', 'HEAD_JOINT', 'Joints', 'Pose',
    'PoseError', 'normalize_joints', 'pose_from_dict', 'save_pose',
    'POSE_FILE_JOINTS', 'BODY_JOINTS', 'JOINT_NAMES',
    'Box', 'Person', 'left_to_right', 'select_players', 'PoseDetector',
    'GestureConfig', 'PoseState', 'classify',
    'Action', 'CountdownScreen', 'CountdownTick', 'Event', 'FinalScreen',
    'GameOver', 'LobbyScreen', 'PlayerMarker', 'PlayerResult',
    'ResultsScreen', 'RetryScreen', 'RoundScored', 'Screen',
    'SnapshotTaken', 'Standing',
    'KP', 'SKELETON', 'PoseFrame', 'Players', 'assign_players',
]

def __getattr__(name):
    """Lazy import to avoid loading all submodules at once."""
    if name == 'Pose':
        from .pose import Pose
        return Pose
    elif name == 'Joints':
        from .pose import Joints
        return Joints
    elif name == 'Point':
        from .pose import Point
        return Point
    elif name == 'JOINT_NAMES':
        from .pose import JOINT_NAMES
        return JOINT_NAMES
    elif name == 'BODY_JOINTS':
        from .pose import BODY_JOINTS
        return BODY_JOINTS
    elif name == 'POSE_FILE_JOINTS':
        from .pose import POSE_FILE_JOINTS
        return POSE_FILE_JOINTS
    elif name == 'HEAD_JOINT':
        from .pose import HEAD_JOINT
        return HEAD_JOINT
    elif name == 'BONES':
        from .pose import BONES
        return BONES
    elif name == 'PoseError':
        from .pose import PoseError
        return PoseError
    elif name == 'normalize_joints':
        from .pose import normalize_joints
        return normalize_joints
    elif name == 'pose_from_dict':
        from .pose import pose_from_dict
        return pose_from_dict
    elif name == 'save_pose':
        from .pose import save_pose
        return save_pose
    elif name == 'Person':
        from .detector import Person
        return Person
    elif name == 'Box':
        from .detector import Box
        return Box
    elif name == 'left_to_right':
        from .detector import left_to_right
        return left_to_right
    elif name == 'select_players':
        from .detector import select_players
        return select_players
    elif name == 'PoseDetector':
        from .detector import PoseDetector
        return PoseDetector
    elif name == 'Action':
        from .screens import Action
        return Action
    elif name == 'CountdownScreen':
        from .screens import CountdownScreen
        return CountdownScreen
    elif name == 'CountdownTick':
        from .screens import CountdownTick
        return CountdownTick
    elif name == 'Event':
        from .screens import Event
        return Event
    elif name == 'FinalScreen':
        from .screens import FinalScreen
        return FinalScreen
    elif name == 'GameOver':
        from .screens import GameOver
        return GameOver
    elif name == 'LobbyScreen':
        from .screens import LobbyScreen
        return LobbyScreen
    elif name == 'PlayerMarker':
        from .screens import PlayerMarker
        return PlayerMarker
    elif name == 'PlayerResult':
        from .screens import PlayerResult
        return PlayerResult
    elif name == 'ResultsScreen':
        from .screens import ResultsScreen
        return ResultsScreen
    elif name == 'RetryScreen':
        from .screens import RetryScreen
        return RetryScreen
    elif name == 'RoundScored':
        from .screens import RoundScored
        return RoundScored
    elif name == 'Screen':
        from .screens import Screen
        return Screen
    elif name == 'SnapshotTaken':
        from .screens import SnapshotTaken
        return SnapshotTaken
    elif name == 'Standing':
        from .screens import Standing
        return Standing
    elif name == 'KP':
        from .types import KP
        return KP
    elif name == 'SKELETON':
        from .types import SKELETON
        return SKELETON
    elif name == 'PoseFrame':
        from .types import PoseFrame
        return PoseFrame
    elif name == 'Players':
        from .types import Players
        return Players
    elif name == 'assign_players':
        from .types import assign_players
        return assign_players
    elif name == 'GestureConfig':
        from .gestures import GestureConfig
        return GestureConfig
    elif name == 'PoseState':
        from .gestures import PoseState
        return PoseState
    elif name == 'classify':
        from .gestures import classify
        return classify
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
