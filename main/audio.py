"""Sounds: optional files in assets/sounds/, with tiny synthesized fallbacks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pygame

RATE = 44100


def init_mixer() -> bool:
    try:
        pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=256)
        return True
    except pygame.error:
        return False


def _to_sound(wave: np.ndarray) -> pygame.mixer.Sound | None:
    if not pygame.mixer.get_init():
        return None
    wave = np.clip(wave, -1.0, 1.0)
    pcm = (wave * 32767 * 0.8).astype(np.int16)
    channels = pygame.mixer.get_init()[2]
    if channels == 2:
        pcm = np.column_stack([pcm, pcm])
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))


def _envelope(n: int, attack: float = 0.005, decay: float | None = None) -> np.ndarray:
    t = np.arange(n) / RATE
    env = np.minimum(1.0, t / attack)
    if decay is not None:
        env *= np.exp(-t / decay)
    else:  # short release at the end to avoid clicks
        rel = int(0.02 * RATE)
        env[-rel:] *= np.linspace(1, 0, rel)
    return env


def tone(freq: float, duration: float, decay: float | None = None) -> pygame.mixer.Sound | None:
    n = int(duration * RATE)
    t = np.arange(n) / RATE
    wave = 0.6 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(4 * np.pi * freq * t)
    return _to_sound(wave * _envelope(n, decay=decay))


def gunshot(duration: float = 0.7, seed: int = 1) -> pygame.mixer.Sound | None:
    n = int(duration * RATE)
    t = np.arange(n) / RATE
    noise = np.random.default_rng(seed).uniform(-1, 1, n)
    crack = noise * np.exp(-t / 0.06)
    boom = np.sin(2 * np.pi * 70 * t * np.exp(-t * 3)) * np.exp(-t / 0.18)
    return _to_sound(1.4 * crack + 0.9 * boom)


def arpeggio(freqs: list[float], step: float = 0.14) -> pygame.mixer.Sound | None:
    n_step = int(step * RATE)
    n = n_step * (len(freqs) + 2)
    wave = np.zeros(n)
    for k, f in enumerate(freqs):
        seg_n = n - k * n_step
        t = np.arange(seg_n) / RATE
        wave[k * n_step :] += 0.35 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.4)
    return _to_sound(wave)


def load_or(path: Path, fallback):
    """The sound file at `path` if it exists and loads, else `fallback()`."""
    if pygame.mixer.get_init() and path.is_file():
        try:
            return pygame.mixer.Sound(str(path))
        except pygame.error as exc:
            print(f"could not load {path}: {exc}; using synthesized sound")
    return fallback()


def play(sound: pygame.mixer.Sound | None) -> None:
    if sound is not None:
        sound.play()
