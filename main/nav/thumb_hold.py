"""Shared hold-to-confirm tracker for splash, menu, and future screens.

Call `update` each frame with the latest gesture snapshot. Returns True once
when the hold duration elapses. Defaults to Thumb_Up; pass `label` for other
confirm gestures (e.g. Closed_Fist on the menu). A different hand showing the
same label is ignored until the confirming hand drops it; releasing resets
progress.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .gestures import GestureSnapshot


@dataclass
class ThumbHoldTracker:
    hold_s: float = 1.0
    min_score: float = 0.5
    label: str = "Thumb_Up"
    match_min_px: float = 80.0
    match_frac: float = 0.15  # of min(frame w, h)
    grace_s: float = 0.0  # tolerate the label dropping for this long (detector flicker)

    _t0: float | None = field(default=None, init=False, repr=False)
    _progress: float = field(default=0.0, init=False, repr=False)
    _fired: bool = field(default=False, init=False, repr=False)
    _hand_anchor: tuple[float, float] | None = field(default=None, init=False, repr=False)
    _last_match: float | None = field(default=None, init=False, repr=False)

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def active(self) -> bool:
        """True while a hold clock is running (including after fire until reset)."""
        return self._t0 is not None

    @property
    def fired(self) -> bool:
        return self._fired

    def reset(self) -> None:
        self._t0 = None
        self._progress = 0.0
        self._fired = False
        self._hand_anchor = None
        self._last_match = None

    def hold_status(self) -> str | None:
        if self.active and not self.fired:
            pretty = self.label.replace("_", " ").upper()
            return f"HOLD {pretty}… {self.progress:.0%}"
        return None

    def update(
        self,
        snap: GestureSnapshot | None,
        timestamp: float,
        *,
        frame_size: tuple[int, int],
        armed: bool = True,
    ) -> bool:
        """Advance or reset the hold. Returns True once when the hold completes."""
        label = effective_label(snap, self.min_score)
        if not armed:
            self.reset()
            return False
        if label != self.label:
            if (
                self._t0 is not None
                and self._last_match is not None
                and timestamp - self._last_match <= self.grace_s
            ):
                # Brief flicker: freeze progress instead of starting over.
                self._t0 = timestamp - self._progress * self.hold_s
                return False
            self.reset()
            return False

        hand = hand_anchor(snap)
        w, h = frame_size
        max_dist = max(self.match_min_px, min(w, h) * self.match_frac)

        if (
            self._hand_anchor is not None
            and hand is not None
            and not _near(hand, self._hand_anchor, max_dist)
        ):
            # Different hand — keep state; re-base so progress does not advance.
            if self._t0 is not None:
                self._t0 = timestamp - (self._progress * self.hold_s)
            return False

        if hand is not None:
            self._hand_anchor = hand
        self._last_match = timestamp
        if self._t0 is None:
            self._t0 = timestamp
        held = timestamp - self._t0
        self._progress = min(1.0, held / self.hold_s) if self.hold_s > 0 else 1.0
        if not self._fired and held >= self.hold_s:
            self._fired = True
            return True
        return False


@dataclass
class ReleaseGate:
    """A fist carried in from the previous page must open before a new hold counts.

    The hand has to show something other than `label` for `open_s` in a row, so a
    one-frame detector flicker on a still-closed fist doesn't count as opening.
    """

    required: bool = True
    open_s: float = 0.12
    min_score: float = 0.5
    label: str = "Closed_Fist"

    _released: bool = field(default=False, init=False, repr=False)
    _open_since: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.reset()

    @property
    def released(self) -> bool:
        return self._released

    def reset(self) -> None:
        self._released = not self.required
        self._open_since = None

    def update(self, snap: GestureSnapshot | None, timestamp: float) -> bool:
        if self._released:
            return True
        if effective_label(snap, self.min_score) == self.label:
            self._open_since = None
            return False
        if self._open_since is None:
            self._open_since = timestamp
        if timestamp - self._open_since >= self.open_s:
            self._released = True
        return self._released


def effective_label(snap: GestureSnapshot | None, min_score: float) -> str | None:
    if snap is None or snap.label is None or snap.score < min_score:
        return None
    return snap.label


def hand_anchor(snap: GestureSnapshot | None) -> tuple[float, float] | None:
    if snap is None:
        return None
    if snap.landmarks:
        return snap.landmarks[0]
    if snap.hand_box is not None:
        x0, y0, x1, y1 = snap.hand_box
        return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    return None


def _near(a: tuple[float, float], b: tuple[float, float], max_dist: float) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= max_dist
