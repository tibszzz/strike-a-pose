"""Wrist ROI crop / upscale / remap helpers (no MediaPipe)."""

import numpy as np

from main.nav.gestures import (
    GestureSnapshot,
    HandGesture,
    HandRoi,
    apply_raised_arm_gate,
    filter_raised_hands,
    hand_rois_from_people,
    pick_gesture_snapshot,
    prepare_roi,
    remap_snapshot,
)
from main.pose import KP
from test_gestures import person


def test_hand_rois_only_from_raised_wrists():
    # One wrist above hip, one hanging below — only the raised side proposes an ROI.
    p = person(
        {
            KP.L_ELBOW: (350, 240),
            KP.L_WRIST: (420, 200),  # above hip (320)
            KP.R_ELBOW: (250, 240),
            KP.R_WRIST: (180, 360),  # below hip
        }
    )
    rois = hand_rois_from_people([p], 640, 480, min_wrist_conf=0.3, scale=2.0, min_px=40, max_rois=2)
    assert len(rois) == 1
    roi = rois[0]
    assert roi.width == roi.height
    lx, ly = float(p.xy[KP.L_WRIST][0]), float(p.xy[KP.L_WRIST][1])
    assert roi.x0 <= lx < roi.x1 and roi.y0 <= ly < roi.y1


def test_hand_rois_empty_when_arms_down():
    assert hand_rois_from_people([person()], 640, 480, min_wrist_conf=0.3, min_px=40) == []


def test_low_wrist_conf_skipped():
    p = person(
        {KP.L_WRIST: (420, 200), KP.R_WRIST: (180, 200)},
        conf=0.1,
    )
    assert hand_rois_from_people([p], 640, 480, min_wrist_conf=0.35) == []


def test_roi_max_limits_candidates():
    p = person(
        {
            KP.L_ELBOW: (350, 240),
            KP.L_WRIST: (420, 200),
            KP.R_ELBOW: (250, 240),
            KP.R_WRIST: (180, 200),
        }
    )
    rois = hand_rois_from_people([p], 640, 480, max_rois=1, min_px=40, scale=2.0)
    assert len(rois) == 1


def test_prepare_roi_and_remap_roundtrip():
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    image[40:100, 50:110] = (0, 255, 0)
    roi = HandRoi(50, 40, 110, 100)
    patch, sx, sy = prepare_roi(image, roi, out_size=120)
    assert patch.shape == (120, 120, 3)
    assert abs(sx - 2.0) < 1e-6 and abs(sy - 2.0) < 1e-6

    # A landmark at the center of the upscaled patch maps to the crop center.
    snap = GestureSnapshot(
        label="Pointing_Up",
        score=0.9,
        hand_box=(10.0, 10.0, 110.0, 110.0),
        landmarks=((60.0, 60.0),),
    )
    mapped = remap_snapshot(snap, roi, sx, sy)
    assert mapped.label == "Pointing_Up"
    mx, my = mapped.landmarks[0]
    assert abs(mx - 80.0) < 1e-6  # 50 + 60/2
    assert abs(my - 70.0) < 1e-6  # 40 + 60/2
    assert mapped.hand_box is not None
    assert abs(mapped.hand_box[0] - 55.0) < 1e-6


def test_raised_arm_gate_rejects_arms_at_sides():
    p = person()  # wrists below hips
    snap = GestureSnapshot(
        label="Pointing_Up",
        score=0.95,
        hand_box=(200.0, 300.0, 280.0, 380.0),
        landmarks=((float(p.xy[KP.R_WRIST][0]), float(p.xy[KP.R_WRIST][1])),),
    )
    gated = apply_raised_arm_gate(snap, [p])
    assert gated.label is None
    assert gated.score == 0.0
    assert gated.landmarks == ()
    assert gated.hand_box is None


def test_raised_arm_gate_allows_raised_hand():
    p = person({KP.R_ELBOW: (250, 160), KP.R_WRIST: (250, 80)})
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=((250.0, 80.0),),
    )
    gated = apply_raised_arm_gate(snap, [p])
    assert gated.label == "Thumb_Up"
    assert gated.score == 0.95
    assert gated.landmarks == snap.landmarks


def test_raised_arm_gate_noop_without_people():
    snap = GestureSnapshot(label="Thumb_Up", score=0.9, landmarks=((10.0, 10.0),))
    assert apply_raised_arm_gate(snap, None).label == "Thumb_Up"
    assert apply_raised_arm_gate(snap, []).label == "Thumb_Up"


def test_filter_raised_hands_keeps_only_raised():
    p = person({KP.R_ELBOW: (250, 160), KP.R_WRIST: (250, 80)})
    raised = HandGesture(
        label="Thumb_Up",
        score=0.9,
        box=(230.0, 60.0, 270.0, 100.0),
        landmarks=((250.0, 80.0),),
    )
    lowered = HandGesture(
        label="Open_Palm",
        score=0.9,
        box=(160.0, 340.0, 200.0, 380.0),
        landmarks=((180.0, 360.0),),
    )
    kept = filter_raised_hands((raised, lowered), [p])
    assert kept == (raised,)


def test_remap_snapshot_maps_hand_landmarks():
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.9,
        hand_box=(10.0, 10.0, 110.0, 110.0),
        landmarks=((60.0, 60.0),),
        hands=(
            HandGesture(
                label="Thumb_Up",
                score=0.9,
                box=(10.0, 10.0, 110.0, 110.0),
                landmarks=((60.0, 60.0), (70.0, 50.0)),
            ),
        ),
    )
    mapped = remap_snapshot(snap, HandRoi(50, 40, 110, 100), 2.0, 2.0)
    assert mapped.hands[0].landmarks == ((80.0, 70.0), (85.0, 65.0))


def test_any_raised_wrists_helper():
    from main.nav.gestures import any_raised_wrists

    assert not any_raised_wrists([person()])
    raised = person({KP.L_WRIST: (355, 200)})
    assert any_raised_wrists([raised])


def test_pick_gesture_snapshot_sticks_to_thumb_hand():
    near = GestureSnapshot(
        label="Thumb_Up", score=0.6, landmarks=((100.0, 200.0), (110.0, 190.0))
    )
    far_better = GestureSnapshot(
        label="Pointing_Up", score=0.99, landmarks=((500.0, 200.0), (510.0, 190.0))
    )
    far_thumb = GestureSnapshot(
        label="Thumb_Up", score=0.95, landmarks=((500.0, 200.0), (510.0, 190.0))
    )

    chosen, sticky = pick_gesture_snapshot([near], None, max_dist=80.0)
    assert chosen is near
    assert sticky == (100.0, 200.0)

    # Higher-scoring other hand must not steal while sticky Thumb_Up remains.
    chosen, sticky = pick_gesture_snapshot(
        [far_better, near], sticky, max_dist=80.0
    )
    assert chosen is near
    assert sticky == (100.0, 200.0)

    # Far Thumb_Up alone — sticky hand gone, allow switch.
    chosen, sticky = pick_gesture_snapshot([far_thumb], sticky, max_dist=80.0)
    assert chosen is far_thumb
    assert sticky == (500.0, 200.0)
