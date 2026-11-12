"""Strike round audio: shutter at snapshot, drumroll into reveal sting."""

from __future__ import annotations

import shutil

import pytest

pytest.importorskip("pygame")

import numpy as np
import pygame

from main import audio
from main.games.strike import play as strike_play
from main.games.strike.play import StrikeGame, _load_sounds
from main.games.strike.screens import (
    CountdownTick,
    ScoreRevealLocked,
    ScoreRevealTick,
    SnapshotTaken,
)
from main.settings import ASSETS, StrikeConfig


@pytest.fixture()
def mixer():
    assert audio.init_mixer()
    yield
    pygame.mixer.stop()


def _cue_recorder(monkeypatch, game) -> list[str]:
    cues: list[str] = []
    names = {id(s): n for n, s in game._sounds.items() if s is not None}

    def record(sound):
        cues.append(names.get(id(sound), "?"))
        if sound is None:
            return None
        return sound.play()

    monkeypatch.setattr(strike_play.audio, "play", record)
    return cues


def test_snapshot_plays_shutter_not_bang(mixer, monkeypatch):
    game = StrikeGame((640, 480), StrikeConfig(rounds=1))
    cues = _cue_recorder(monkeypatch, game)

    game._on_logic_event(SnapshotTaken(round_number=1))

    assert cues == ["shutter"]


def test_countdown_ticks_still_play_on_final_three(mixer, monkeypatch):
    game = StrikeGame((640, 480), StrikeConfig(rounds=1))
    cues = _cue_recorder(monkeypatch, game)

    for n in (5, 4, 3, 2, 1):
        game._on_logic_event(CountdownTick(seconds_left=n))

    assert cues == ["tick", "tick", "tick"]


def test_strike_tick_ignores_duel_ready_wav(mixer, tmp_path):
    """Duel's ready.wav must not override Strike's countdown synth."""
    ready = ASSETS / "sounds" / "ready.wav"
    assert ready.is_file()
    shutil.copy(ready, tmp_path / "ready.wav")

    sounds = _load_sounds(tmp_path)
    tick = sounds["tick"]
    duel_ready = pygame.mixer.Sound(str(tmp_path / "ready.wav"))
    assert tick is not None
    # Synth tone is ~0.25s; ready.wav is ~0.63s.
    assert tick.get_length() == pytest.approx(0.25, abs=0.05)
    assert duel_ready.get_length() == pytest.approx(0.63, abs=0.05)


def test_score_reveal_starts_drumroll_once_then_sting(mixer, monkeypatch):
    game = StrikeGame((640, 480), StrikeConfig(rounds=1, results_reveal_s=0.4))
    cues = _cue_recorder(monkeypatch, game)

    game._on_logic_event(ScoreRevealTick(scores=(10, 20)))
    game._on_logic_event(ScoreRevealTick(scores=(30, 40)))
    game._on_logic_event(ScoreRevealLocked(scores=(50, 60)))

    assert cues == ["drumroll", "sting"]
    assert game._drumroll_channel is None


def test_camera_shutter_synth_returns_sound(mixer):
    sound = audio.camera_shutter()
    assert sound is not None
    assert sound.get_length() > 0


def test_drumroll_synth_lasts_about_the_reveal(mixer):
    sound = audio.drumroll(0.5, hz=10.0)
    assert sound is not None
    assert 0.45 <= sound.get_length() <= 0.55


def test_drumroll_synth_gets_louder(mixer):
    sound = audio.drumroll(0.6, hz=10.0)
    assert sound is not None
    mono = pygame.sndarray.array(sound)
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    n = len(mono)
    early = float(np.abs(mono[: n // 5]).mean())
    late = float(np.abs(mono[3 * n // 5 :]).mean())
    assert late > early * 1.5


def test_drumroll_hits_at_constant_reveal_rate(mixer):
    hz = 10.0
    sound = audio.drumroll(1.0, hz=hz)
    assert sound is not None
    mono = pygame.sndarray.array(sound)
    if mono.ndim == 2:
        mono = mono.mean(axis=1)
    # Energy in each 1/hz window should be similar — steady pace, not a rush.
    window = int(audio.RATE / hz)
    energies = [
        float(np.abs(mono[i : i + window]).mean())
        for i in range(0, len(mono) - window, window)
    ]
    assert len(energies) >= 8
    # Crescendo is fine; intervals must stay filled (no sparse early / dense late).
    assert min(energies) > 0
    early_gap = energies[1] / energies[0]
    late_gap = energies[-1] / energies[-2]
    assert 0.5 < early_gap < 3.0
    assert 0.5 < late_gap < 3.0


def test_reveal_sting_synth_returns_sound(mixer):
    sound = audio.reveal_sting()
    assert sound is not None
    assert sound.get_length() > 0
