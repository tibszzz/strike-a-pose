"""Who's playing? Thumbs-up / thumbs-down confirmation before a dodgeball match.

Pure logic (no MediaPipe, pygame or camera) so it can be unit tested. Each frame
gets the pose detections and the recognised hands; people are followed by
position, and a gesture held for a moment inside someone's box sets them as
playing (thumbs up) or sitting out (thumbs down).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol, Sequence

THUMB_UP = "Thumb_Up"
THUMB_DOWN = "Thumb_Down"

PENDING = "pending"
PLAYING = "playing"
OUT = "out"


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
    """Someone in front of the camera during the confirm screen."""

    box: tuple[float, float, float, float]
    status: str = PENDING
    gesture: str | None = None  # thumb currently shown (for drawing)
    hold_frames: int = 0  # how long `gesture` has been held
    missing: int = 0  # frames since last detected
    id: int = field(default=0)

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def visible(self) -> bool:
        return self.missing == 0


class Roster:
    def __init__(
        self,
        width: float,
        max_players: int = 3,
        hold_frames: int = 8,
        forget_frames: int = 30,
        min_score: float = 0.5,
    ) -> None:
        self.width = width
        self.max_players = max_players
        self.hold_frames = hold_frames  # gesture must be held this long to count
        self.forget_frames = forget_frames  # drop someone missing this long
        self.min_score = min_score
        self.candidates: list[Candidate] = []
        self.full = False  # a thumbs-up was refused because all slots are taken
        self._next_id = 1

    # -- queries -------------------------------------------------------------

    @property
    def players(self) -> list[Candidate]:
        """Confirmed players, left to right (P1..Pn)."""
        return sorted((c for c in self.candidates if c.status == PLAYING), key=lambda c: c.center_x)

    @property
    def pending(self) -> list[Candidate]:
        return [c for c in self.candidates if c.status == PENDING and c.visible]

    @property
    def visible(self) -> list[Candidate]:
        return sorted((c for c in self.candidates if c.visible), key=lambda c: c.center_x)

    # -- updates -------------------------------------------------------------

    def clear(self) -> None:
        """Everyone back to undecided."""
        for c in self.candidates:
            c.status = PENDING
            c.gesture = None
            c.hold_frames = 0
        self.full = False

    def update(self, people: Sequence[_Person], hands: Iterable[_Hand]) -> None:
        self._track(people)
        shown = self._gestures_by_candidate(hands)
        self.full = False
        for c in self.candidates:
            if not c.visible:
                c.gesture, c.hold_frames = None, 0
                continue
            label = shown.get(c.id)
            if label is None or label != c.gesture:
                c.gesture, c.hold_frames = label, (1 if label else 0)
            else:
                c.hold_frames += 1
            if c.gesture and c.hold_frames >= self.hold_frames:
                self._apply(c, c.gesture)

    def _apply(self, c: Candidate, label: str) -> None:
        if label == THUMB_DOWN:
            c.status = OUT
        elif label == THUMB_UP and c.status != PLAYING:
            if len(self.players) < self.max_players:
                c.status = PLAYING
            else:
                self.full = True

    def _track(self, people: Sequence[_Person]) -> None:
        """Match detections to known candidates by nearest centre x."""
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
            cand.box = tuple(map(float, people[pi].box))
            cand.missing = 0
        for ci, cand in enumerate(self.candidates):
            if ci not in used_c:
                cand.missing += 1
        self.candidates = [c for c in self.candidates if c.missing <= self.forget_frames]
        for pi, person in enumerate(people):
            if pi not in used_p:
                self.candidates.append(Candidate(box=tuple(map(float, person.box)), id=self._next_id))
                self._next_id += 1

    def _gestures_by_candidate(self, hands: Iterable[_Hand]) -> dict[int, str]:
        """Thumb gesture each visible candidate is showing (best-scoring hand wins)."""
        best: dict[int, tuple[float, str]] = {}
        visible = [c for c in self.candidates if c.visible]
        for hand in hands:
            if hand.label not in (THUMB_UP, THUMB_DOWN) or hand.score < self.min_score:
                continue
            hx, hy = hand.center
            owners = [c for c in visible if _contains(c.box, hx, hy, margin=0.15)]
            if not owners:
                continue
            owner = min(owners, key=lambda c: abs(c.center_x - hx))
            if owner.id not in best or hand.score > best[owner.id][0]:
                best[owner.id] = (hand.score, hand.label)
        return {cid: label for cid, (_, label) in best.items()}


def _contains(box: tuple[float, float, float, float], x: float, y: float, margin: float) -> bool:
    """Point inside the box, grown by `margin` of its width/height on each side."""
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    return x1 - mx <= x <= x2 + mx and y1 - my <= y <= y2 + my
