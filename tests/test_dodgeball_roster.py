"""Dodgeball thumbs-up / thumbs-down roster (no camera, no MediaPipe)."""

from dataclasses import dataclass

from main.games.dodgeball.roster import OUT, PENDING, PLAYING, THUMB_DOWN, THUMB_UP, Roster

HOLD = 3


@dataclass(frozen=True)
class P:
    box: tuple[float, float, float, float]

    @property
    def center_x(self) -> float:
        return (self.box[0] + self.box[2]) / 2


@dataclass(frozen=True)
class H:
    label: str
    x: float
    y: float = 300
    score: float = 0.9

    @property
    def center(self):
        return (self.x, self.y)


def person(x: float) -> P:
    return P((x - 100, 100, x + 100, 600))


def run(roster: Roster, people, hands, frames: int = HOLD) -> None:
    for _ in range(frames):
        roster.update(people, hands)


def make(**kw) -> Roster:
    return Roster(1280, hold_frames=HOLD, **kw)


def test_new_people_start_pending():
    r = make()
    r.update([person(300), person(900)], [])
    assert [c.status for c in r.visible] == [PENDING, PENDING]
    assert r.players == []


def test_thumb_up_must_be_held():
    r = make()
    people = [person(300)]
    run(r, people, [H(THUMB_UP, 300)], frames=HOLD - 1)
    assert r.players == []
    r.update(people, [H(THUMB_UP, 300)])
    assert [c.status for c in r.players] == [PLAYING]


def test_flicker_resets_hold():
    r = make()
    people = [person(300)]
    run(r, people, [H(THUMB_UP, 300)], frames=HOLD - 1)
    r.update(people, [])
    run(r, people, [H(THUMB_UP, 300)], frames=HOLD - 1)
    assert r.players == []


def test_gesture_goes_to_person_whose_box_holds_the_hand():
    r = make()
    people = [person(300), person(900)]
    run(r, people, [H(THUMB_UP, 900), H(THUMB_DOWN, 300)])
    left, right = r.visible
    assert (left.status, right.status) == (OUT, PLAYING)


def test_hand_outside_everyone_is_ignored():
    r = make()
    run(r, [person(300)], [H(THUMB_UP, 1200)])
    assert r.players == []


def test_thumb_down_removes_a_confirmed_player():
    r = make()
    people = [person(300)]
    run(r, people, [H(THUMB_UP, 300)])
    run(r, people, [H(THUMB_DOWN, 300)])
    assert r.players == [] and r.visible[0].status == OUT


def test_low_score_and_other_gestures_ignored():
    r = make()
    run(r, [person(300)], [H(THUMB_UP, 300, score=0.3), H("Open_Palm", 300)])
    assert r.players == []


def test_max_players_enforced():
    r = make(max_players=2)
    people = [person(200), person(640), person(1080)]
    run(r, people, [H(THUMB_UP, 200), H(THUMB_UP, 640), H(THUMB_UP, 1080)])
    assert len(r.players) == 2
    assert r.full


def test_status_follows_person_as_they_move():
    r = make()
    run(r, [person(300)], [H(THUMB_UP, 300)])
    for x in range(300, 600, 40):  # walk right in small steps
        r.update([person(x)], [])
    assert len(r.players) == 1 and r.players[0].center_x == 580


def test_players_ordered_left_to_right():
    r = make()
    people = [person(900), person(300)]
    run(r, people, [H(THUMB_UP, 900)])
    run(r, people, [H(THUMB_UP, 300)])
    assert [c.center_x for c in r.players] == [300, 900]


def test_missing_person_forgotten_after_timeout():
    r = make(forget_frames=5)
    run(r, [person(300)], [H(THUMB_UP, 300)])
    run(r, [], [], frames=5)
    assert len(r.players) == 1  # briefly lost: still in
    r.update([], [])
    assert r.players == []


def test_clear_resets_everyone():
    r = make()
    people = [person(300), person(900)]
    run(r, people, [H(THUMB_UP, 300), H(THUMB_DOWN, 900)])
    r.clear()
    assert [c.status for c in r.visible] == [PENDING, PENDING]
