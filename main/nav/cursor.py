"""Smoothed hand cursor for the menu, how-to-play and results pages.

Raw MediaPipe landmarks jitter, drop out for a frame or two, and the index
fingertip jumps when the hand closes into a fist. `HandCursor` turns them into
a steady pointer:

- It follows the *palm centre* (wrist + finger knuckles), which barely moves
  between an open palm and a fist, so closing the hand doesn't knock the
  cursor off a button.
- A One-Euro filter smooths it: heavy smoothing when the hand is nearly still
  (no jitter), light smoothing when it moves fast (no lag).
- Brief dropouts (< `grace_s`) keep the cursor where it was instead of
  hiding / re-anchoring it, so a flickery detection doesn't make it skip.
- Reach scales with the player's body. The hand is matched to the person
  whose YOLO wrist it sits on, and a reach zone is laid around that person's
  shoulders in *torso lengths* (`Reach`). Standing far away (small in frame)
  or close up (big in frame) then takes the same arm movement to hit the
  screen edges, and where you stand in the frame doesn't matter.
- Without a matched body (no pose, or no shoulders visible) it falls back to a
  fixed `gain` around the screen centre.

Two modes:
- absolute (menu, results): the reach zone maps onto the whole screen
  (fallback: centre + (palm − centre) × gain).
- relative (how-to-play): mouse-like. Starts parked at `start`, moves by the
  hand's movement × (screen size / reach zone size) (fallback: × gain),
  re-anchors after the hand has been gone longer than `grace_s`; clamping at
  an edge naturally drags the anchor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .hand_geometry import palm_center

Point = tuple[float, float]

_DEFAULT_DT = 1 / 30


@dataclass
class OneEuro:
    """One-Euro low-pass filter for a 2D point (Casiez et al. 2012)."""

    min_cutoff: float = 1.0  # Hz; lower = smoother at rest
    beta: float = 0.02  # speed coefficient; higher = less lag when moving fast
    d_cutoff: float = 1.0  # Hz; cutoff for the speed estimate

    _x: Point | None = field(default=None, init=False, repr=False)
    _dx: Point = field(default=(0.0, 0.0), init=False, repr=False)
    _t: float | None = field(default=None, init=False, repr=False)

    def reset(self) -> None:
        self._x = None
        self._dx = (0.0, 0.0)
        self._t = None

    def __call__(self, p: Point, t: float) -> Point:
        if self._x is None or self._t is None:
            self._x, self._t = p, t
            return p
        dt = t - self._t
        if dt <= 0:
            dt = _DEFAULT_DT
        self._t = t
        a_d = _alpha(self.d_cutoff, dt)
        raw_dx = ((p[0] - self._x[0]) / dt, (p[1] - self._x[1]) / dt)
        dx = (self._dx[0] + a_d * (raw_dx[0] - self._dx[0]), self._dx[1] + a_d * (raw_dx[1] - self._dx[1]))
        self._dx = dx
        cutoff = self.min_cutoff + self.beta * math.hypot(*dx)
        a = _alpha(cutoff, dt)
        x = (self._x[0] + a * (p[0] - self._x[0]), self._x[1] + a * (p[1] - self._x[1]))
        self._x = x
        return x


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (math.tau * max(cutoff, 1e-6))
    return 1.0 / (1.0 + tau / dt)


@dataclass(frozen=True)
class Reach:
    """Reach zone around the player's shoulder midpoint, in torso lengths.

    The zone spans `half_w` left and right of the shoulders, from `top` above
    the shoulder line down to `bottom` below it, and maps onto the screen.
    """

    half_w: float = 0.9
    top: float = 1.1
    bottom: float = 0.3


MIN_KP_CONF = 0.35
L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST, L_HIP, R_HIP = 5, 6, 9, 10, 11, 12


def body_frame(person: object, min_conf: float = MIN_KP_CONF) -> tuple[Point, float] | None:
    """(shoulder midpoint, torso length) in px, or None without both shoulders.

    Torso length = shoulders→hips; with the hips out of frame (standing close)
    it is estimated as 1.3 × shoulder width.
    """
    xy = getattr(person, "xy", None)
    conf = getattr(person, "conf", None)
    if xy is None or conf is None or len(conf) <= R_HIP:
        return None
    if conf[L_SHOULDER] < min_conf or conf[R_SHOULDER] < min_conf:
        return None
    ls, rs = (float(xy[L_SHOULDER][0]), float(xy[L_SHOULDER][1])), (float(xy[R_SHOULDER][0]), float(xy[R_SHOULDER][1]))
    shoulders = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
    width = math.hypot(ls[0] - rs[0], ls[1] - rs[1])
    if conf[L_HIP] >= min_conf and conf[R_HIP] >= min_conf:
        hips = ((float(xy[L_HIP][0]) + float(xy[R_HIP][0])) / 2, (float(xy[L_HIP][1]) + float(xy[R_HIP][1])) / 2)
        torso = math.hypot(shoulders[0] - hips[0], shoulders[1] - hips[1])
    else:
        torso = 1.3 * width
    if torso < 10:
        return None
    return shoulders, torso


def hand_owner(people: object, hand: Point, min_conf: float = MIN_KP_CONF) -> tuple[Point, float] | None:
    """Body frame of the person whose wrist is nearest `hand` (within one torso length)."""
    best: tuple[float, tuple[Point, float]] | None = None
    for person in people or ():
        body = body_frame(person, min_conf)
        if body is None:
            continue
        xy, conf = person.xy, person.conf  # type: ignore[attr-defined]
        for k in (L_WRIST, R_WRIST):
            if conf[k] < min_conf:
                continue
            d = math.hypot(float(xy[k][0]) - hand[0], float(xy[k][1]) - hand[1])
            if d <= body[1] and (best is None or d < best[0]):
                best = (d, body)
    return best[1] if best else None


def hand_point(snap: object | None) -> Point | None:
    """Palm centre of the primary hand in canvas px, or None."""
    landmarks = getattr(snap, "landmarks", None) if snap is not None else None
    if not landmarks:
        return None
    return palm_center(landmarks)


class HandCursor:
    """Steady pointer from gesture snapshots. Call `update` once per frame."""

    def __init__(
        self,
        size: tuple[int, int],
        *,
        relative: bool = False,
        gain: float = 1.0,
        grace_s: float = 0.35,
        min_cutoff: float = 1.0,
        beta: float = 0.02,
        smooth: bool = True,
        start: Point | None = None,
        reach: Reach | None = None,
        body_hold_s: float = 1.0,
    ) -> None:
        self.w, self.h = size
        self.relative = relative
        self.gain = gain
        self.grace_s = grace_s
        self.smooth = smooth
        self.reach = reach
        self.body_hold_s = body_hold_s
        self._filter = OneEuro(min_cutoff=min_cutoff, beta=beta)
        self._body_filter = OneEuro(min_cutoff=0.6, beta=0.004)  # body moves slowly
        self._start = start if start is not None else (self.w / 2, self.h / 2)
        self.reset()

    # -- state ---------------------------------------------------------------

    def reset(self) -> None:
        self._filter.reset()
        self._pos: Point | None = self._start if self.relative else None
        self._anchor: Point | None = None  # last smoothed hand point (relative mode)
        self._last_seen: float | None = None
        self._tracking = False
        self._body_filter.reset()
        self._body: tuple[Point, float] | None = None  # smoothed (shoulders, torso)
        self._body_seen: float | None = None

    @property
    def position(self) -> Point | None:
        """Cursor in canvas px; None (absolute mode) when no hand is around."""
        return self._pos

    @property
    def body(self) -> tuple[Point, float] | None:
        """Smoothed (shoulder midpoint, torso length) of the hand's owner, if known."""
        return self._body

    @property
    def tracking(self) -> bool:
        """True when a hand was seen this frame."""
        return self._tracking

    # -- update ------------------------------------------------------------------

    def update(self, snap: object | None, timestamp: float, people: object = None) -> Point | None:
        """Advance with this frame's gesture snapshot (and `PoseFrame.people` for reach)."""
        raw = hand_point(snap)
        if raw is None:
            self._tracking = False
            gone = self._last_seen is None or timestamp - self._last_seen > self.grace_s
            if gone:
                self._filter.reset()
                self._anchor = None  # relative: next sighting re-anchors (like lifting a mouse)
                if not self.relative:
                    self._pos = None
            return self._pos

        self._tracking = True
        self._last_seen = timestamp
        p = self._filter(raw, timestamp) if self.smooth else raw
        body = self._update_body(raw, people, timestamp)
        if self.relative:
            if self._anchor is not None and self._pos is not None:
                gx, gy = self._rel_gains(body)
                x = self._pos[0] + (p[0] - self._anchor[0]) * gx
                y = self._pos[1] + (p[1] - self._anchor[1]) * gy
                self._pos = self._clamp(x, y)
            self._anchor = p
        elif body is not None and self.reach is not None:
            (sx, sy), torso = body
            r = self.reach
            x = self.w / 2 + (p[0] - sx) / (r.half_w * torso) * (self.w / 2)
            y = (p[1] - (sy - r.top * torso)) / ((r.top + r.bottom) * torso) * self.h
            self._pos = self._clamp(x, y)
        else:
            cx, cy = self.w / 2, self.h / 2
            self._pos = self._clamp(cx + (p[0] - cx) * self.gain, cy + (p[1] - cy) * self.gain)
        return self._pos

    def _update_body(self, hand: Point, people: object, timestamp: float) -> tuple[Point, float] | None:
        """Smoothed body frame of the hand's owner; held briefly when YOLO misses a frame."""
        if self.reach is None:
            return None
        found = hand_owner(people, hand)
        if found is None:
            if self._body_seen is None or timestamp - self._body_seen > self.body_hold_s:
                self._body = None
                self._body_filter.reset()
            return self._body
        (sx, sy), torso = found
        if self._body is not None and math.hypot(sx - self._body[0][0], sy - self._body[0][1]) > self._body[1]:
            self._body_filter.reset()  # someone else's hand now
            self._body = None
        if self.smooth:
            shoulders = self._body_filter((sx, sy), timestamp)
            prev = self._body[1] if self._body is not None else torso
            torso = prev + 0.15 * (torso - prev)
        else:
            shoulders = (sx, sy)
        self._body = (shoulders, torso)
        self._body_seen = timestamp
        return self._body

    def _rel_gains(self, body: tuple[Point, float] | None) -> tuple[float, float]:
        if body is None or self.reach is None:
            return self.gain, self.gain
        torso, r = body[1], self.reach
        return (self.w / 2) / (r.half_w * torso), self.h / ((r.top + r.bottom) * torso)

    def hand_point_for(self, screen: Point) -> Point:
        """Absolute mode: the hand position that puts the cursor on `screen`."""
        cx, cy = self.w / 2, self.h / 2
        return (cx + (screen[0] - cx) / self.gain, cy + (screen[1] - cy) / self.gain)

    def _clamp(self, x: float, y: float) -> Point:
        return (min(max(x, 0.0), float(self.w - 1)), min(max(y, 0.0), float(self.h - 1)))


def nav_cursor(size: tuple[int, int], *, relative: bool = False, config: object | None = None) -> HandCursor:
    """HandCursor tuned from `GestureNavConfig` (env-overridable)."""
    from .gestures import load_gesture_nav_config

    cfg = config or load_gesture_nav_config()
    reach = (
        Reach(half_w=cfg.reach_half_w, top=cfg.reach_top, bottom=cfg.reach_bottom)
        if cfg.reach_body
        else None
    )
    return HandCursor(
        size,
        relative=relative,
        gain=cfg.cursor_rel_gain if relative else cfg.cursor_gain,
        grace_s=cfg.cursor_grace_s,
        min_cutoff=cfg.cursor_min_cutoff,
        beta=cfg.cursor_beta,
        reach=reach,
    )
