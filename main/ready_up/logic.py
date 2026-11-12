"""Shared ready-up: who is in frame, who is ready, when the match may start.

Pure logic (no pygame / MediaPipe). Games feed detections + hands each frame
and react when `update` returns a frozen roster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol, Sequence

THUMB_UP = "Thumb_Up"
CLOSED_FIST = "Closed_Fist"


class _Person(Protocol):
    box: tuple[float, float, float, float]

    @property
    def center_x(self) -> float: ...


class _Hand(Protocol):
    label: str
    score: float

    @property
    def center(self) -> tuple[float, float]: ...


@dataclass
class Candidate:
    """Someone visible during ready-up (tracked across frames by position)."""

    box: tuple[float, float, float, float]
    ready: bool = False
    gesture: str | None = None
    hold_frames: int = 0
    hold_miss: int = 0  # consecutive frames without the held thumb (grace budget)
    fist_hold_frames: int = 0
    missing: int = 0
    id: int = field(default=0)
    nose: tuple[float, float] | None = None
    person: object | None = None  # last matched detection (game-specific type)

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def visible(self) -> bool:
        return self.missing == 0


@dataclass(frozen=True)
class ReadyUpConfig:
    min_players: int
    max_players: int
    title: str
    how_to_lines: tuple[str, ...]
    pose_stills: tuple[Path, ...] = ()
    hold_frames: int = 8
    # Tolerate detector flicker so a one-frame Thumb_Up dropout does not wipe hold.
    hold_grace_frames: int = 6  # ~0.2s at 30fps (matches shell hold_grace_s)
    fist_hold_frames: int = 15  # ~0.5s at 30fps
    forget_frames: int = 30
    min_score: float = 0.5
    # `--debug`: allow a single ready player even when min_players > 1 (solo testing).
    debug: bool = False

    @property
    def required_min(self) -> int:
        """Players needed to start; debug floors this at 1."""
        return 1 if self.debug else self.min_players


@dataclass(frozen=True)
class Started:
    """Frozen L→R roster of ready players at the moment of start."""

    roster: tuple[object, ...]  # detections captured at start


@dataclass
class ReadyUp:
    def __init__(self, width: float, config: ReadyUpConfig) -> None:
        self.width = width
        self.config = config
        self.candidates: list[Candidate] = []
        self._next_id = 1
        self.started: Started | None = None

    def reset(self) -> None:
        self.candidates.clear()
        self._next_id = 1
        self.started = None

    @property
    def eligible(self) -> list[Candidate]:
        """Leftmost max_players visible people (provisional P1…Pn)."""
        visible = sorted(
            (c for c in self.candidates if c.visible), key=lambda c: c.center_x
        )
        return visible[: self.config.max_players]

    @property
    def ready_players(self) -> list[Candidate]:
        return sorted(
            (c for c in self.eligible if c.ready), key=lambda c: c.center_x
        )

    @property
    def ready_count(self) -> int:
        return len(self.ready_players)

    @property
    def can_start(self) -> bool:
        n = self.ready_count
        return self.config.required_min <= n <= self.config.max_players

    def force_start(self) -> Started | None:
        """Debug escape: start if enough people are ready (solo OK when config.debug)."""
        if not self.can_start:
            return None
        return self._freeze()

    def update(
        self,
        people: Sequence[_Person],
        hands: Iterable[_Hand] = (),
    ) -> Started | None:
        """Track people, apply thumbs-up ready and fist-to-start. Once per start."""
        if self.started is not None:
            return None
        self._track(people)
        self._enforce_eligibility()
        thumbs, fists = self._gestures_by_candidate(hands)
        for c in self.candidates:
            if not c.visible:
                c.gesture, c.hold_frames, c.hold_miss = None, 0, 0
                c.fist_hold_frames = 0
                c.ready = False
                continue
            label = thumbs.get(c.id)
            if label is None:
                if c.gesture is not None and c.hold_frames > 0:
                    c.hold_miss += 1
                    if c.hold_miss > self.config.hold_grace_frames:
                        c.gesture, c.hold_frames, c.hold_miss = None, 0, 0
                else:
                    c.gesture, c.hold_frames, c.hold_miss = None, 0, 0
            elif label != c.gesture:
                c.gesture, c.hold_frames, c.hold_miss = label, 1, 0
            else:
                c.hold_frames += 1
                c.hold_miss = 0
            if (
                c in self.eligible
                and c.gesture == THUMB_UP
                and c.hold_frames >= self.config.hold_frames
            ):
                c.ready = True

            if c in self.eligible and c.ready and c.id in fists:
                c.fist_hold_frames += 1
            else:
                c.fist_hold_frames = 0

        if self.can_start:
            for c in self.ready_players:
                if c.fist_hold_frames >= self.config.fist_hold_frames:
                    return self._freeze()
        return None

    def _freeze(self) -> Started:
        roster = tuple(
            c.person if c.person is not None else c for c in self.ready_players
        )
        self.started = Started(roster=roster)
        return self.started

    def _enforce_eligibility(self) -> None:
        eligible_ids = {c.id for c in self.eligible}
        for c in self.candidates:
            if c.id not in eligible_ids:
                c.ready = False
                c.fist_hold_frames = 0

    def _track(self, people: Sequence[_Person]) -> None:
        max_dist = self.width * 0.2
        pairs = sorted(
            (abs(c.center_x - p.center_x), ci, pi)
            for ci, c in enumerate(self.candidates)
            for pi, p in enumerate(people)
        )
        used_c: set[int] = set()
        used_p: set[int] = set()
        for dist, ci, pi in pairs:
            if dist > max_dist or ci in used_c or pi in used_p:
                continue
            used_c.add(ci)
            used_p.add(pi)
            cand = self.candidates[ci]
            person = people[pi]
            cand.box = tuple(map(float, person.box))
            cand.missing = 0
            cand.person = person
            cand.nose = _nose_of(person)
        for ci, cand in enumerate(self.candidates):
            if ci not in used_c:
                cand.missing += 1
        self.candidates = [
            c for c in self.candidates if c.missing <= self.config.forget_frames
        ]
        for pi, person in enumerate(people):
            if pi not in used_p:
                self.candidates.append(
                    Candidate(
                        box=tuple(map(float, person.box)),
                        id=self._next_id,
                        person=person,
                        nose=_nose_of(person),
                    )
                )
                self._next_id += 1

    def hand_owner(self, hand: _Hand) -> Candidate | None:
        """The visible candidate whose box holds this hand (nearest centre wins)."""
        hx, hy = hand.center
        owners = [
            c for c in self.candidates if c.visible and _contains(c.box, hx, hy, margin=0.15)
        ]
        if not owners:
            return None
        return min(owners, key=lambda c: abs(c.center_x - hx))

    def hold_progress(self, c: Candidate, label: str) -> float | None:
        """0..1 progress of the hold `label` is driving for `c`, or None if it does nothing.

        Thumbs up (not yet ready) fills toward ready; a closed fist from a ready
        player fills toward starting the match when the lobby can start.
        """
        if c not in self.eligible:
            return None
        cfg = self.config
        if label == THUMB_UP and not c.ready:
            held = c.hold_frames if c.gesture == THUMB_UP else 0
            return min(1.0, held / max(1, cfg.hold_frames))
        if label == CLOSED_FIST and c.ready and self.can_start:
            return min(1.0, c.fist_hold_frames / max(1, cfg.fist_hold_frames))
        return None

    def actionable_holds(
        self, hands: Iterable[_Hand]
    ) -> list[tuple[tuple[float, float], str, float]]:
        """Per-hand fist badges to draw: (center, label, progress).

        Every Closed_Fist on a ready player when the lobby can start. Thumbs-up
        ready has no hold badge (P-marker colour is the ready signal).
        """
        out: list[tuple[tuple[float, float], str, float]] = []
        for hand in hands:
            if hand.score < self.config.min_score or hand.label != CLOSED_FIST:
                continue
            owner = self.hand_owner(hand)
            if owner is None:
                continue
            progress = self.hold_progress(owner, CLOSED_FIST)
            if progress is not None:
                out.append((hand.center, CLOSED_FIST, progress))
        return out

    def _gestures_by_candidate(
        self, hands: Iterable[_Hand]
    ) -> tuple[dict[int, str], set[int]]:
        """Thumb_Up label per candidate, and which candidate ids show Closed_Fist."""
        best_thumb: dict[int, tuple[float, str]] = {}
        fists: set[int] = set()
        for hand in hands:
            if hand.score < self.config.min_score:
                continue
            owner = self.hand_owner(hand)
            if owner is None:
                continue
            if hand.label == THUMB_UP:
                if owner.id not in best_thumb or hand.score > best_thumb[owner.id][0]:
                    best_thumb[owner.id] = (hand.score, hand.label)
            elif hand.label == CLOSED_FIST:
                fists.add(owner.id)
        thumbs = {cid: label for cid, (_, label) in best_thumb.items()}
        return thumbs, fists


def _nose_of(person: object) -> tuple[float, float] | None:
    xy = getattr(person, "xy", None)
    conf = getattr(person, "conf", None)
    if xy is not None and conf is not None:
        try:
            if float(conf[0]) >= 0.3:
                return (float(xy[0][0]), float(xy[0][1]))
        except (IndexError, TypeError, ValueError):
            return None
        return None
    joints = getattr(person, "joints", None)
    if isinstance(joints, dict) and "nose" in joints:
        x, y = joints["nose"]
        return (float(x), float(y))
    return None


def _contains(
    box: tuple[float, float, float, float], x: float, y: float, margin: float
) -> bool:
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    return x1 - mx <= x <= x2 + mx and y1 - my <= y <= y2 + my


def match_roster_slots(
    people: Sequence[_Person], seeds_x: Sequence[float]
) -> list[_Person | None]:
    """Map detections onto a frozen L→R roster by nearest centre x.

    Unfilled seats stay None when fewer people than seeds are available.
    """
    n = len(seeds_x)
    if n == 0:
        return []
    pairs = sorted(
        (abs(seeds_x[s] - p.center_x), s, i)
        for s in range(n)
        for i, p in enumerate(people)
    )
    used_s: set[int] = set()
    used_i: set[int] = set()
    slots: list[_Person | None] = [None] * n
    for _, s, i in pairs:
        if s in used_s or i in used_i:
            continue
        used_s.add(s)
        used_i.add(i)
        slots[s] = people[i]
        if len(used_s) == n:
            break
    return slots


def match_roster_by_seeds(
    people: Sequence[_Person], seeds_x: Sequence[float]
) -> list[_Person] | None:
    """Map current detections onto a frozen L→R roster by nearest centre x.

    Returns None when fewer people than seeds are available.
    """
    slots = match_roster_slots(people, seeds_x)
    if any(person is None for person in slots):
        return None
    return [person for person in slots if person is not None]
