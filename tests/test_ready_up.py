"""Ready-up pure logic: candidates, ready toggle, start gate, roster freeze."""

from __future__ import annotations

from dataclasses import dataclass

from main.ready_up.logic import (
    CLOSED_FIST,
    THUMB_DOWN,
    THUMB_UP,
    ReadyUp,
    ReadyUpConfig,
    match_roster_by_seeds,
)


@dataclass
class FakePerson:
    box: tuple[float, float, float, float]
    tag: str = ""

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2


@dataclass
class FakeHand:
    label: str
    score: float
    center: tuple[float, float]


def cfg(**kwargs) -> ReadyUpConfig:
    base = dict(
        min_players=2,
        max_players=4,
        title="TEST",
        how_to_lines=("do the thing",),
        hold_frames=2,
        fist_hold_frames=2,
        forget_frames=5,
    )
    base.update(kwargs)
    return ReadyUpConfig(**base)


def person(cx: float, tag: str = "", half: float = 40.0) -> FakePerson:
    return FakePerson(box=(cx - half, 100, cx + half, 400), tag=tag)


def hand_at(label: str, cx: float, cy: float = 200.0) -> FakeHand:
    return FakeHand(label=label, score=0.9, center=(cx, cy))


def hold_thumb(ready: ReadyUp, people, label: str, cx: float, frames: int = 3) -> None:
    for _ in range(frames):
        ready.update(people, [hand_at(label, cx)])


def test_leftmost_max_are_eligible_extras_ignored():
    ready = ReadyUp(1000, cfg(max_players=2))
    people = [person(100, "a"), person(300, "b"), person(500, "c")]
    ready.update(people)
    assert [c.center_x for c in ready.eligible] == [100.0, 300.0]


def test_thumb_up_then_down_toggles_ready():
    ready = ReadyUp(1000, cfg(min_players=1, max_players=2))
    p = person(200, "solo")
    hold_thumb(ready, [p], THUMB_UP, 200)
    assert ready.ready_count == 1
    hold_thumb(ready, [p], THUMB_DOWN, 200)
    assert ready.ready_count == 0


def test_cannot_start_below_min_ready():
    ready = ReadyUp(1000, cfg(min_players=2, max_players=4))
    people = [person(100), person(300)]
    hold_thumb(ready, people, THUMB_UP, 100)
    assert not ready.can_start
    assert ready.update(people, [hand_at(CLOSED_FIST, 100)]) is None


def test_closed_fist_from_ready_player_starts_and_freezes_ltr_roster():
    ready = ReadyUp(1000, cfg(min_players=2, max_players=4))
    a, b = person(300, "right"), person(100, "left")
    people = [a, b]
    hold_thumb(ready, people, THUMB_UP, 100)
    hold_thumb(ready, people, THUMB_UP, 300)
    assert ready.can_start
    started = None
    for _ in range(3):
        started = ready.update(people, [hand_at(CLOSED_FIST, 100)])
        if started is not None:
            break
    assert started is not None
    assert [p.tag for p in started.roster] == ["left", "right"]
    # Second start attempt is ignored until reset
    assert ready.update(people, [hand_at(CLOSED_FIST, 100)]) is None


def test_force_start_debug_requires_ready_window():
    ready = ReadyUp(1000, cfg(min_players=1, max_players=2, debug=True))
    p = person(150, "p")
    assert ready.force_start() is None
    hold_thumb(ready, [p], THUMB_UP, 150)
    started = ready.force_start()
    assert started is not None
    assert started.roster[0].tag == "p"


def test_missing_person_clears_ready():
    ready = ReadyUp(1000, cfg(min_players=1, max_players=2, forget_frames=10))
    p = person(200, "solo")
    hold_thumb(ready, [p], THUMB_UP, 200)
    assert ready.ready_count == 1
    ready.update([])  # disappeared this frame
    assert ready.ready_count == 0
    assert all(not c.ready for c in ready.candidates)


def test_match_roster_by_seeds_picks_nearest():
    seeds = [100.0, 400.0]
    people = [person(95, "a"), person(500, "b"), person(250, "extra")]
    matched = match_roster_by_seeds(people, seeds)
    assert matched is not None
    assert [p.tag for p in matched] == ["a", "b"]


def test_match_roster_by_seeds_none_when_short():
    assert match_roster_by_seeds([person(100)], [100.0, 400.0]) is None


# --- ready-up page chrome --------------------------------------------------------


def test_start_hint_reports_who_is_missing_then_invites_the_fist():
    from main.ready_up.draw import _join_sub, _start_sub

    ready = ReadyUp(1000, cfg())
    ready.update([], [])
    assert _join_sub(ready) == "Step in front of the camera."
    people = [person(200), person(600)]
    ready.update(people, [])
    assert _join_sub(ready) == "Thumbs down to sit out."
    assert _start_sub(ready) == "Need 2 players ready."
    hold_thumb(ready, people, THUMB_UP, 200)
    hold_thumb(ready, people, THUMB_UP, 600)
    assert _start_sub(ready) == "2 ready. Close your hand to play."
    assert _start_sub(ReadyUp(1000, cfg(min_players=1))) == "Need 1 player ready."


def test_draw_ready_up_smoke_with_ready_and_waiting_players():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from main.ready_up.draw import draw_ready_up
    from main.styles import STRIKE

    pygame.init()
    ready = ReadyUp(640, cfg())
    people = [person(150), person(450)]
    ready.update(people, [])
    hold_thumb(ready, people, THUMB_UP, 150)
    draw_ready_up(pygame.Surface((640, 480)), ready, theme=STRIKE)
