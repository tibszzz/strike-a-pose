"""Unit tests for bang→draw replay buffer and slow-mo sampling."""

import numpy as np

from main.games.duel.replay import ReplayClip, ReplayPlayback, ReplayRecorder


def _bgr(w, h, value):
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = value
    return img


def test_recorder_trims_to_bang_through_end():
    rec = ReplayRecorder(scale=0.5)
    rec.start(1.0)
    rec.push(_bgr(40, 20, (0, 0, 10)), 0.5)  # before bang — ignored
    rec.push(_bgr(40, 20, (0, 0, 20)), 1.0)
    rec.push(_bgr(40, 20, (0, 0, 30)), 1.1)
    rec.push(_bgr(40, 20, (0, 0, 40)), 1.2)
    rec.push(_bgr(40, 20, (0, 0, 50)), 1.4)  # after end — dropped by trim
    clip = rec.clip(1.2)
    assert clip is not None
    assert clip.bang_time == 1.0 and clip.end_time == 1.2
    assert clip.timestamps == (1.0, 1.1, 1.2)
    assert clip.frames[0].shape == (10, 20, 3)  # half-res
    assert not rec.active


def test_recorder_discard_clears():
    rec = ReplayRecorder(scale=1.0)
    rec.start(0.0)
    rec.push(_bgr(8, 8, (1, 2, 3)), 0.0)
    rec.discard()
    assert rec.clip(1.0) is None
    assert not rec.active


def test_playback_slowmo_then_freeze():
    frames = tuple(np.full((4, 4, 3), i, np.uint8) for i in (10, 20, 30))
    clip = ReplayClip(timestamps=(0.0, 0.1, 0.2), frames=frames, bang_time=0.0, end_time=0.2)
    play = ReplayPlayback(clip, speed=0.25, freeze=0.5)
    assert play.motion_duration() == 0.8
    assert play.duration() == 1.3

    rgb0, ms0, impact0 = play.sample(0.0)
    assert not impact0 and ms0 == 0.0 and rgb0[0, 0, 0] == 10

    rgb_mid, ms_mid, impact_mid = play.sample(0.4)  # source t = 0.1
    assert not impact_mid
    assert ms_mid == 100.0
    assert rgb_mid[0, 0, 0] == 20

    rgb_hit, ms_hit, impact_hit = play.sample(0.8)
    assert impact_hit and ms_hit == 200.0 and rgb_hit[0, 0, 0] == 30

    rgb_freeze, ms_freeze, impact_freeze = play.sample(1.2)
    assert impact_freeze and ms_freeze == 200.0 and rgb_freeze[0, 0, 0] == 30
