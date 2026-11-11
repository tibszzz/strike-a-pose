"""Wrist ROI crop / upscale / remap helpers (no MediaPipe)."""

import numpy as np

from main.nav.gestures import (
    GestureSnapshot,
    HandRoi,
    apply_thumb_pose_gate,
    hand_rois_from_people,
    prepare_roi,
    remap_snapshot,
)
from main.pose import KP
from test_gestures import person


def test_hand_rois_from_visible_wrists():
    # Arms out: wrists far from elbows → large crops.
    p = person(
        {
            KP.L_ELBOW: (350, 240),
            KP.L_WRIST: (420, 240),
            KP.R_ELBOW: (250, 240),
            KP.R_WRIST: (180, 240),
        }
    )
    rois = hand_rois_from_people([p], 640, 480, min_wrist_conf=0.3, scale=2.0, min_px=40, max_rois=2)
    assert len(rois) == 2
    for roi in rois:
        assert roi.width == roi.height
        assert 0 <= roi.x0 < roi.x1 <= 640
        assert 0 <= roi.y0 < roi.y1 <= 480
        # Wrist should land inside the crop.
        assert any(
            roi.x0 <= float(p.xy[w][0]) < roi.x1 and roi.y0 <= float(p.xy[w][1]) < roi.y1
            for w in (KP.L_WRIST, KP.R_WRIST)
        )


def test_low_wrist_conf_skipped():
    p = person({KP.L_WRIST: (420, 240), KP.R_WRIST: (180, 240)}, conf=0.1)
    assert hand_rois_from_people([p], 640, 480, min_wrist_conf=0.35) == []


def test_roi_max_limits_candidates():
    p = person(
        {
            KP.L_ELBOW: (350, 240),
            KP.L_WRIST: (420, 240),
            KP.R_ELBOW: (250, 240),
            KP.R_WRIST: (180, 240),
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


def test_thumb_gate_rejects_arms_at_sides():
    p = person()  # wrists hang below elbows
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=((float(p.xy[KP.R_WRIST][0]), float(p.xy[KP.R_WRIST][1])),),
    )
    gated = apply_thumb_pose_gate(snap, [p])
    assert gated.label is None
    assert gated.landmarks == snap.landmarks


def test_thumb_gate_allows_raised_hand():
    p = person({KP.R_ELBOW: (250, 160), KP.R_WRIST: (250, 80)})
    snap = GestureSnapshot(
        label="Thumb_Up",
        score=0.95,
        landmarks=((250.0, 80.0),),
    )
    gated = apply_thumb_pose_gate(snap, [p])
    assert gated.label == "Thumb_Up"
    assert gated.score == 0.95


def test_thumb_gate_noop_without_people():
    snap = GestureSnapshot(label="Thumb_Up", score=0.9, landmarks=((10.0, 10.0),))
    assert apply_thumb_pose_gate(snap, None).label == "Thumb_Up"
    assert apply_thumb_pose_gate(snap, []).label == "Thumb_Up"


def test_thumb_gate_ignores_other_labels():
    p = person()
    snap = GestureSnapshot(label="Pointing_Up", score=0.9, landmarks=((245.0, 315.0),))
    assert apply_thumb_pose_gate(snap, [p]).label == "Pointing_Up"
