import random

import pytest

from main.settings import DuelConfig, GestureConfig, GestureNavConfig, Messages, env, from_env


def test_gesture_nav_hold_default_is_half_second():
    assert GestureNavConfig().thumb_hold_s == 0.5


def test_from_env_overrides_only_set_fields(monkeypatch):
    monkeypatch.setenv("LIVES", "5")
    monkeypatch.setenv("DRAW_TIMEOUT", "2.25")
    monkeypatch.setenv("SETTLE_TIME", "")  # blank = default
    cfg = from_env(DuelConfig)
    assert cfg.lives == 5 and cfg.draw_timeout == 2.25
    assert cfg.settle_time == DuelConfig().settle_time


def test_from_env_gesture_config(monkeypatch):
    monkeypatch.setenv("MAX_ARM_TILT", "45")
    assert from_env(GestureConfig).max_arm_tilt == 45.0
    monkeypatch.setenv("MIN_FOREARM_RISE", "8")
    assert from_env(GestureConfig).min_forearm_rise == 8.0


def test_bad_value_names_the_setting(monkeypatch):
    monkeypatch.setenv("LIVES", "three")
    with pytest.raises(ValueError, match="LIVES"):
        from_env(DuelConfig)


def test_env_helper(monkeypatch):
    monkeypatch.delenv("CAMERA", raising=False)
    assert env("CAMERA", 0) == 0
    monkeypatch.setenv("CAMERA", "2")
    assert env("CAMERA", 0) == 2


def test_example_env_parses_to_defaults(monkeypatch, tmp_path):
    from pathlib import Path

    from dotenv import dotenv_values

    values = dotenv_values(Path(__file__).parent.parent / ".env.example")
    assert values["DEVICE"] == ""  # inline comments are stripped
    for k, v in values.items():
        monkeypatch.setenv(k, v or "")
    assert from_env(DuelConfig) == DuelConfig()
    assert from_env(GestureConfig) == GestureConfig()


def test_messages_skip_empty_and_avoid_repeats():
    m = Messages(["", "A", "B", "  "], "fallback", random.Random(0))
    assert m.items == ["A", "B"]
    picks = [m.pick() for _ in range(10)]
    assert all(a != b for a, b in zip(picks, picks[1:]))


def test_messages_fallback_when_empty():
    assert Messages([], "hi").pick() == "hi"


def test_cursor_scale_defaults_and_env(monkeypatch):
    assert GestureNavConfig().cursor_scale == 1.5
    monkeypatch.setenv("CURSOR_SCALE", "2.0")
    assert from_env(GestureNavConfig).cursor_scale == 2.0
