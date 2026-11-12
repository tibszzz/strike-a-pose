"""Crop math for duel side-camera PiPs. No pygame — keep it unit-testable."""

from __future__ import annotations

from dataclasses import dataclass

from main.pose import Person

Box = tuple[float, float, float, float]  # x1, y1, x2, y2


def pad_box(box: Box, pad_frac: float, frame_w: float, frame_h: float) -> Box:
    """Grow `box` by `pad_frac` of its size on each side, clamped to the frame."""
    x1, y1, x2, y2 = box
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    px, py = w * pad_frac, h * pad_frac
    return _clamp((x1 - px, y1 - py, x2 + px, y2 + py), frame_w, frame_h)


def aspect_expand(box: Box, target_aspect: float, frame_w: float, frame_h: float) -> Box:
    """Expand the shorter side around the center so width/height == `target_aspect`.

    Clamped to the frame. If the frame itself can't hold the aspect at this size,
    the box is as large as fits while preferring the requested aspect.
    """
    if target_aspect <= 0:
        return _clamp(box, frame_w, frame_h)
    x1, y1, x2, y2 = box
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if w / h < target_aspect:
        w = h * target_aspect
    else:
        h = w / target_aspect
    # If expansion exceeds the frame, shrink uniformly to fit while keeping aspect.
    scale = min(1.0, frame_w / w, frame_h / h)
    w, h = w * scale, h * scale
    return _clamp((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), frame_w, frame_h)


def smooth_box(prev: Box | None, target: Box, alpha: float) -> Box:
    """EMA toward `target`. `alpha` in (0, 1]; first sample snaps."""
    if prev is None or alpha >= 1:
        return target
    a = max(0.0, min(1.0, alpha))
    return tuple(p + a * (t - p) for p, t in zip(prev, target))  # type: ignore[return-value]


def crop_source(box: Box, target_aspect: float, pad_frac: float, frame_w: float, frame_h: float) -> Box:
    """Pad then aspect-expand a detection box into a PiP crop."""
    return aspect_expand(pad_box(box, pad_frac, frame_w, frame_h), target_aspect, frame_w, frame_h)


def cover_crop(src_w: float, src_h: float, dest_w: float, dest_h: float) -> Box:
    """Center-crop of `src` that matches `dest` aspect (cover-fit, no letterbox)."""
    if src_w <= 0 or src_h <= 0 or dest_w <= 0 or dest_h <= 0:
        return (0.0, 0.0, max(0.0, src_w), max(0.0, src_h))
    src_aspect = src_w / src_h
    dest_aspect = dest_w / dest_h
    if src_aspect > dest_aspect:
        w = src_h * dest_aspect
        return ((src_w - w) / 2, 0.0, w, src_h)
    h = src_w / dest_aspect
    return (0.0, (src_h - h) / 2, src_w, h)


@dataclass
class PreviewTracker:
    """Per-side crop tracker: smooth while present, grace-hold, then None."""

    pad: float = 0.18
    smooth: float = 0.35
    grace: float = 0.3
    target_aspect: float = 0.4  # width/height; portrait

    _box: Box | None = None
    _last_seen: float | None = None

    def update(
        self,
        person: Person | None,
        now: float,
        frame_w: float,
        frame_h: float,
    ) -> Box | None:
        if person is not None:
            target = crop_source(person.box, self.target_aspect, self.pad, frame_w, frame_h)
            self._box = smooth_box(self._box, target, self.smooth)
            self._last_seen = now
            return self._box
        if self._box is not None and self._last_seen is not None and now - self._last_seen <= self.grace:
            return self._box
        self._box = None
        self._last_seen = None
        return None

    def reset(self) -> None:
        self._box = None
        self._last_seen = None


def resolve_results_portrait(
    tracker: PreviewTracker,
    person: Person | None,
    *,
    now: float,
    frame_w: float,
    frame_h: float,
) -> Box | None:
    """RESULTS portrait slot: live tracked crop, or None → fallback art.

    v1 fills with the gameplay PiP crop. v2 can swap this slot to stick-only art.
    """
    return tracker.update(person, now, frame_w, frame_h)


def _clamp(box: Box, frame_w: float, frame_h: float) -> Box:
    x1, y1, x2, y2 = box
    x1 = min(max(0.0, x1), frame_w)
    y1 = min(max(0.0, y1), frame_h)
    x2 = min(max(0.0, x2), frame_w)
    y2 = min(max(0.0, y2), frame_h)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return (x1, y1, x2, y2)
