"""Bang→draw frame buffer and slow-mo playback math. No pygame — keep it unit-testable."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True)
class ReplayClip:
    """Downscaled RGB frames from bang through first confirmed draw."""

    timestamps: tuple[float, ...]
    frames: tuple[np.ndarray, ...]  # RGB uint8
    bang_time: float
    end_time: float

    def __post_init__(self) -> None:
        if len(self.timestamps) != len(self.frames):
            raise ValueError("timestamps and frames length mismatch")
        if not self.frames:
            raise ValueError("empty replay clip")


@dataclass
class ReplayRecorder:
    """Collects half-res RGB frames while BANG is live; trim on hit."""

    scale: float = 0.5
    _bang_time: float | None = None
    _timestamps: list[float] = field(default_factory=list)
    _frames: list[np.ndarray] = field(default_factory=list)
    _active: bool = False

    def start(self, bang_time: float) -> None:
        self.discard()
        self._bang_time = bang_time
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    def push(self, image_bgr: np.ndarray, timestamp: float) -> None:
        if not self._active or self._bang_time is None:
            return
        if timestamp < self._bang_time:
            return
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        scale = max(1e-6, self.scale)
        if scale != 1.0:
            h, w = rgb.shape[:2]
            rgb = cv2.resize(
                rgb,
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        self._timestamps.append(timestamp)
        self._frames.append(np.ascontiguousarray(rgb))

    def discard(self) -> None:
        self._bang_time = None
        self._timestamps.clear()
        self._frames.clear()
        self._active = False

    def clip(self, end_time: float) -> ReplayClip | None:
        """Trim to [bang_time, end_time] and stop recording. None if nothing usable."""
        if self._bang_time is None or not self._frames:
            self.discard()
            return None
        bang = self._bang_time
        end = max(bang, end_time)
        ts: list[float] = []
        frames: list[np.ndarray] = []
        for t, f in zip(self._timestamps, self._frames):
            if t < bang:
                continue
            if t > end:
                break
            ts.append(t)
            frames.append(f)
        self.discard()
        if not frames:
            return None
        # Ensure the impact moment is represented: if last stamp is before end, keep last.
        return ReplayClip(tuple(ts), tuple(frames), bang, end)


@dataclass
class ReplayPlayback:
    """Maps wall-clock elapsed time to a slow-mo source frame + reaction clock."""

    clip: ReplayClip
    speed: float = 0.25
    freeze: float = 0.6

    def motion_duration(self) -> float:
        span = max(0.0, self.clip.end_time - self.clip.bang_time)
        return span / max(1e-6, self.speed)

    def duration(self) -> float:
        return self.motion_duration() + max(0.0, self.freeze)

    def sample(self, elapsed_wall: float) -> tuple[np.ndarray, float, bool]:
        """Return (rgb, reaction_ms, at_impact) for wall time since replay start."""
        motion = self.motion_duration()
        at_impact = elapsed_wall >= motion
        if at_impact:
            source_t = self.clip.end_time
            frame = self.clip.frames[-1]
        else:
            source_t = self.clip.bang_time + max(0.0, elapsed_wall) * max(1e-6, self.speed)
            source_t = min(source_t, self.clip.end_time)
            frame = self._frame_at(source_t)
        reaction_ms = (min(source_t, self.clip.end_time) - self.clip.bang_time) * 1000.0
        return frame, reaction_ms, at_impact

    def _frame_at(self, source_t: float) -> np.ndarray:
        ts = self.clip.timestamps
        # Last frame with timestamp <= source_t; if none, first frame.
        idx = 0
        for i, t in enumerate(ts):
            if t <= source_t:
                idx = i
            else:
                break
        return self.clip.frames[idx]
