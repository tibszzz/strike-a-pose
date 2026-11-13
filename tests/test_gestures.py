import numpy as np

from main.pose import (
    KP,
    GestureConfig,
    Person,
    PoseState,
    assign_players,
    classify,
    is_arm_extended,
    is_wrist_raised,
)

# Image coordinates: y grows downward. A person facing the camera, ~1:1 scale.
BASE = {
    KP.NOSE: (300, 100),
    KP.L_SHOULDER: (340, 160), KP.R_SHOULDER: (260, 160),
    KP.L_HIP: (330, 320), KP.R_HIP: (270, 320),
    KP.L_KNEE: (330, 420), KP.R_KNEE: (270, 420),
    KP.L_ANKLE: (330, 520), KP.R_ANKLE: (270, 520),
}
ARMS_DOWN = {
    KP.L_ELBOW: (350, 240), KP.L_WRIST: (355, 360),
    KP.R_ELBOW: (250, 240), KP.R_WRIST: (245, 360),
}


def person(overrides=None, conf=0.9, box=(220, 80, 380, 540)):
    pts = {**BASE, **ARMS_DOWN, **(overrides or {})}
    xy = np.zeros((17, 2), dtype=np.float32)  # same dtype YOLO returns
    for i, p in pts.items():
        xy[i] = p
    return Person(xy=xy, conf=np.full(17, conf, dtype=np.float32), box=box)


def test_arms_down_is_neutral():
    assert classify(person()) == PoseState.NEUTRAL


def test_right_arm_pointing_sideways_is_drawn():
    p = person({KP.R_ELBOW: (190, 160), KP.R_WRIST: (120, 150)})
    assert is_arm_extended(p, "right")
    assert classify(p) == PoseState.DRAWN


def test_left_arm_pointing_sideways_is_drawn():
    p = person({KP.L_ELBOW: (410, 160), KP.L_WRIST: (480, 150)})
    assert classify(p) == PoseState.DRAWN


def test_forearm_level_or_sagging_is_not_drawn():
    # Straight, level arm, but the wrist isn't above the elbow (rise <= 0 deg < 5 deg).
    level = person({KP.R_ELBOW: (190, 160), KP.R_WRIST: (120, 160)})
    sagging = person({KP.R_ELBOW: (190, 162), KP.R_WRIST: (120, 165)})
    assert not is_arm_extended(level, "right")
    assert not is_arm_extended(sagging, "right")


def test_min_forearm_rise_is_configurable():
    # Wrist ~3.3 deg above the elbow: below the 5 deg default, fine at 2 deg.
    p = person({KP.R_ELBOW: (190, 160), KP.R_WRIST: (120, 156)})
    assert not is_arm_extended(p, "right")
    assert is_arm_extended(p, "right", GestureConfig(min_forearm_rise=2.0))


def test_arm_raised_overhead_is_not_drawn():
    p = person({KP.R_ELBOW: (255, 90), KP.R_WRIST: (250, 20)})
    assert classify(p) == PoseState.NEUTRAL


def test_bent_elbow_is_not_drawn():
    p = person({KP.R_ELBOW: (190, 162), KP.R_WRIST: (200, 90)})
    assert not is_arm_extended(p, "right")


def test_hands_on_chest_is_neutral():
    p = person({KP.R_WRIST: (290, 200), KP.L_WRIST: (310, 200)})
    assert classify(p) == PoseState.NEUTRAL


def test_low_confidence_is_not_drawn():
    p = person({KP.R_ELBOW: (190, 160), KP.R_WRIST: (120, 150)}, conf=0.2)
    assert classify(p) == PoseState.NEUTRAL


def test_missing():
    assert classify(None) == PoseState.MISSING


def test_assign_players_by_x():
    left = person(box=(100, 0, 300, 500))
    right = person(box=(700, 0, 900, 500))
    assert assign_players([right, left], 1000) == (left, right)


def test_lone_player_placed_by_half():
    p = person(box=(700, 0, 900, 500))
    assert assign_players([p], 1000) == (None, p)
    assert assign_players([], 1000) == (None, None)


def test_arms_down_wrists_not_raised():
    p = person()  # default wrists hang below hips
    assert not is_wrist_raised(p, "left")
    assert not is_wrist_raised(p, "right")


def test_wrist_at_hip_is_not_raised():
    p = person({KP.R_WRIST: (245, 320)})  # same y as R_HIP
    assert not is_wrist_raised(p, "right")


def test_raised_hand_wrist_is_raised():
    # Wrist above hip (y smaller).
    p = person({KP.R_ELBOW: (250, 160), KP.R_WRIST: (250, 80)})
    assert is_wrist_raised(p, "right")
    assert not is_wrist_raised(p, "left")


def test_wrist_between_elbow_and_hip_is_not_raised():
    # Hands-on-hips / waist: above hip but still below the elbow.
    p = person({KP.R_ELBOW: (250, 200), KP.R_WRIST: (250, 280)})
    assert not is_wrist_raised(p, "right")
