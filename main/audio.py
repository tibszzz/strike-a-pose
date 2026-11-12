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


def camera_shutter(duration: float = 0.18, seed: int = 3) -> pygame.mixer.Sound | None:
    """Short mechanical click for a camera snapshot."""
    n = int(duration * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    click = rng.uniform(-1, 1, n) * np.exp(-t / 0.01)
    body = np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.022)
    thud = np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.035)
    # Hotter mix so it reads clearly over the live room / after `_to_sound`'s 0.8.
    return _to_sound(1.8 * click + 1.2 * body + 0.9 * thud)


def drumroll(
    duration: float = 2.0,
    hz: float = 20.0,
    seed: int = 11,
) -> pygame.mixer.Sound | None:
    """High taps at a steady `hz`, getting louder over `duration` seconds.

    `hz` should match the score-reveal flash rate so each number change lands
    with a hit.
    """
    n = max(1, int(duration * RATE))
    wave = np.zeros(n)
    rng = np.random.default_rng(seed)
    interval = 1.0 / hz if hz > 0 else duration
    hits = list(np.arange(0.0, duration, interval))
    for hit_t in hits:
        progress = hit_t / duration if duration > 0 else 1.0
        amp = 0.18 + 0.82 * progress**1.4
        start = int(hit_t * RATE)
        length = int(0.035 * RATE)
        end = min(n, start + length)
        if start >= end:
            continue
        seg_n = end - start
        seg_t = np.arange(seg_n) / RATE
        noise = rng.uniform(-1, 1, seg_n) * np.exp(-seg_t / 0.012)
        body = np.sin(2 * np.pi * 620 * seg_t) * np.exp(-seg_t / 0.02)
        ring = np.sin(2 * np.pi * 1240 * seg_t) * np.exp(-seg_t / 0.015)
        wave[start:end] += amp * (0.55 * noise + 0.55 * body + 0.35 * ring)
    peak = np.max(np.abs(wave)) or 1.0
    return _to_sound(wave / peak)


def reveal_sting(duration: float = 0.55, seed: int = 19) -> pygame.mixer.Sound | None:
    """Bright hit that lands the score reveal."""
    n = int(duration * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    crack = rng.uniform(-1, 1, n) * np.exp(-t / 0.04)
    low = np.sin(2 * np.pi * 98 * t) * np.exp(-t / 0.22)
    mid = np.sin(2 * np.pi * 392 * t) * np.exp(-t / 0.16)
    high = np.sin(2 * np.pi * 784 * t) * np.exp(-t / 0.1)
    return _to_sound(0.7 * crack + 0.9 * low + 0.55 * mid + 0.35 * high)


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


def play(sound: pygame.mixer.Sound | None) -> pygame.mixer.Channel | None:
    if sound is None:
        return None
    return sound.play()


def play_then(first: pygame.mixer.Sound | None, then: pygame.mixer.Sound | None) -> None:
    """Play `first`, with `then` queued on the same channel right after it."""
    if first is None:
        play(then)
        return
    channel = first.play()
    if channel is not None and then is not None:
        channel.queue(then)
