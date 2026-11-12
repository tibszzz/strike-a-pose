"""How-to-play page shown between the menu and a game's ready-up.

Title + two note buttons (Let's go! / Back) across the top, three illustrated
notebook cards, and the game's key fact along the bottom. Hovering a button
selects it (the selection sticks after the cursor leaves); Closed_Fist held
anywhere then presses it. Nothing is selected when the page opens, so a fist
does nothing until a button has been hovered.

The cursor is mouse-like: it starts parked at the centre of the screen and
follows the hand's *movement* (not its absolute spot), re-anchoring whenever
the hand is lost. A fist carried over from the menu pick therefore can't land
on a button, and must open once before any new hold counts. Pushing the
cursor against a screen edge drags its offset, so the hand never runs out of
room.

Art lives in `assets/ui/how_to_play/<game id>/step_{1,2,3}.png` + `info.png`;
swap the files to restyle without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pygame

from main import content
from main.nav import (
    GestureSnapshot,
    MenuCommand,
    Nav,
    StartGame,
    ThumbHoldTracker,
    effective_label,
    load_gesture_nav_config,
)
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import PoseFrame
from main.ui import paper, widgets
from main.ui.paper import UI, Frame
from main.ui.widgets import Hint

copy = content.HowToPlay

ART = UI / "how_to_play"

PLAY, BACK = 0, 1

# Card left edges in design px (mockups), shared width / top / bottom.
_CARD_X = (125, 572, 1018)
_CARD_W = 410
_CARD_TOP, _CARD_BOTTOM = 222, 688


@dataclass(frozen=True)
class Guide:
    title: str
    steps: tuple[tuple[str, str], tuple[str, str], tuple[str, str]]
    fact: tuple[str, str]


def guide_for(game_id: str, facts: Mapping[str, object] | None = None) -> Guide:
    """Copy for `game_id` with {lives} / {rounds} / … filled from `facts`."""
    title, steps, fact = copy.guides[game_id]
    values = _SafeFacts(facts or {})

    def fill(pair: tuple[str, str]) -> tuple[str, str]:
        return (pair[0].format_map(values), pair[1].format_map(values))

    return Guide(title=title, steps=tuple(fill(s) for s in steps), fact=fill(fact))  # type: ignore[arg-type]


class _SafeFacts(dict):
    def __init__(self, facts: Mapping[str, object]) -> None:
        super().__init__(facts)

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class HowToPlayGame:
    """Implements the shell Game protocol; emits StartGame(game_id) or StartGame(None)."""

    is_how_to = True
    owns_gestures = True  # shell must not feed rising-edge MenuCommands
    wants_gestures = True
    gesture_hands = NAV_GESTURE_HANDS
    background = paper.BACKDROP

    def __init__(
        self,
        size: tuple[int, int],
        game_id: str,
        *,
        facts: Mapping[str, object] | None = None,
        release_first: bool = True,
    ) -> None:
        self.w, self.h = size
        self.frame = Frame(self.w, self.h)
        self.game_id = game_id
        self.guide = guide_for(game_id, facts)
        self.title = self.guide.title
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._min_score = cfg.min_score
        self._thumb = ThumbHoldTracker(
            hold_s=cfg.thumb_hold_s, min_score=cfg.min_score, label="Closed_Fist"
        )
        self._release_first = release_first
        self._released = not release_first
        self._lock: int | None = None  # button under the cursor
        self._pending: Nav | None = None
        self._cursor: tuple[float, float] = (self.w / 2, self.h / 2)
        self._offset: tuple[float, float] | None = None  # cursor - fingertip

    # -- layout ----------------------------------------------------------------

    def card_rects(self) -> list[pygame.Rect]:
        return [self.frame.rect(x, _CARD_TOP, x + _CARD_W, _CARD_BOTTOM) for x in _CARD_X]

    def button_rects(self) -> list[pygame.Rect]:
        """[Let's go!, Back] top-right, level with the title strip."""
        f = self.frame
        return [f.rect(964, 84, 1232, 188), f.rect(1254, 90, 1428, 184)]

    @property
    def cursor(self) -> tuple[float, float]:
        return self._cursor

    # -- Game protocol -----------------------------------------------------------

    def reset(self) -> None:
        self._thumb.reset()
        self._released = not self._release_first
        self._lock = None
        self._pending = None
        self._cursor = (self.w / 2, self.h / 2)
        self._offset = None

    def update(self, frame: PoseFrame) -> None:
        snap = self.gesture_snapshot
        if not self._released and effective_label(snap, self._min_score) != "Closed_Fist":
            self._released = True

        hand = self._track_cursor(snap)
        if hand and not self._thumb.active:
            # Hover selects; the selection sticks when the cursor leaves the button.
            for i, rect in enumerate(self.button_rects()):
                if rect.collidepoint(self._cursor) and self._lock != i:
                    self._lock = i
                    self._thumb.reset()
                    break

        if self._thumb.update(
            snap,
            frame.timestamp,
            frame_size=(self.w, self.h),
            armed=self._released and self._lock is not None,
        ):
            assert self._lock is not None
            self._confirm(self._lock)

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        f = self.frame
        paper.draw_backdrop(canvas)
        widgets.draw_title_strip(canvas, f, self.guide.title, seed=sum(map(ord, self.game_id)))

        art_dir = ART / self.game_id
        for i, (rect, (heading, sub)) in enumerate(zip(self.card_rects(), self.guide.steps)):
            widgets.draw_step_card(
                canvas, f, rect, i + 1, art_dir / f"step_{i + 1}.png", heading, sub, seed=40 + i
            )

        widgets.draw_hint_bar(
            canvas,
            f,
            f.rect(122, 718, 560, 818),
            (Hint(art_dir / "info.png", *self.guide.fact),),
        )

        for idx, (rect, label) in enumerate(zip(self.button_rects(), (copy.play, copy.back))):
            widgets.draw_note_button(
                canvas,
                f,
                rect,
                idx + 1,
                label,
                selected=self._lock == idx,
                seed=60 + idx,
                label_size=42,
                progress=self._thumb.progress if self._lock == idx else 0.0,
            )

        widgets.draw_cursor(canvas, f, self.gesture_snapshot, self._thumb.progress, at=self._cursor)

    def handle_command(self, command: MenuCommand) -> None:
        """Debug keyboard: arrows pick a button, Enter confirms (Let's go! if none), Back → menu."""
        if command in (MenuCommand.MOVE_UP, MenuCommand.MOVE_DOWN):
            self._lock = BACK if self._lock in (None, PLAY) else PLAY
        elif command is MenuCommand.SELECT:
            self._confirm(self._lock if self._lock is not None else PLAY)
        elif command is MenuCommand.BACK:
            self._confirm(BACK)

    def poll_nav(self) -> Nav | None:
        nav, self._pending = self._pending, None
        return nav

    def debug_lines(self) -> list[str]:
        snap = self.gesture_snapshot
        label = snap.label if snap and snap.label else "-"
        target = {PLAY: "play", BACK: "back"}.get(self._lock, "-")
        return [f"how-to {self.game_id} → {target}", f"gesture {label}"]

    # -- helpers -------------------------------------------------------------------

    def _track_cursor(self, snap: GestureSnapshot | None) -> bool:
        """Move the relative cursor with the fingertip. Returns True while a hand is seen."""
        tip = widgets.pointer(snap)
        if tip is None:
            self._offset = None  # hand lost: next sighting re-anchors (like lifting a mouse)
            return False
        if self._offset is None:
            self._offset = (self._cursor[0] - tip[0], self._cursor[1] - tip[1])
        x = min(max(tip[0] + self._offset[0], 0.0), float(self.w - 1))
        y = min(max(tip[1] + self._offset[1], 0.0), float(self.h - 1))
        # Clamped at an edge → the offset follows, so the hand can always reach a button.
        self._offset = (x - tip[0], y - tip[1])
        self._cursor = (x, y)
        return True

    def _confirm(self, idx: int) -> None:
        self._pending = StartGame(None) if idx == BACK else StartGame(self.game_id)
