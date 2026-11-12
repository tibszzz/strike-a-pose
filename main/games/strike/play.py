"""Strike play path on the shared pygame shell + PoseTracker."""

from __future__ import annotations

from typing import Sequence

import cv2
import pygame

from main import content, styles
from main.nav import GestureSnapshot, ThumbHoldTracker, load_gesture_nav_config
from main.nav.hand_geometry import NAV_GESTURE_HANDS
from main.pose import PoseFrame
from main.pose.library import Pose, from_coco_person, load_library
from main.pose.types import Person as CocoPerson
from main.ready_up import ReadyUp, ReadyUpConfig, Started, draw_ready_up
from main.settings import ASSETS, StrikeConfig

from .game import compose, overlay_results_hold
from .logic import Game as StrikeLogic
from .screens import LobbyScreen, ResultsScreen, Screen


def _still_paths() -> tuple:
    root = ASSETS / "ready_up" / "strike"
    return tuple(sorted(root.glob("pose_*.png")))


class StrikeGame:
    title = content.Strike.window_title
    background = styles.STRIKE.bg

    def __init__(
        self,
        size: tuple[int, int],
        config: StrikeConfig | None = None,
        poses: Sequence[Pose] | None = None,
    ) -> None:
        self.w, self.h = size
        self._config = config if config is not None else StrikeConfig()
        library = list(poses) if poses is not None else load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._screen: Screen = LobbyScreen(
            markers=(),
            can_start=False,
            min_players=self._config.min_players,
            max_players=self._config.max_players,
        )
        self._image = None
        self._confirm = False
        self.gesture_snapshot: GestureSnapshot | None = None
        cfg = load_gesture_nav_config()
        self._thumb = ThumbHoldTracker(hold_s=cfg.thumb_hold_s, min_score=cfg.min_score)
        self._in_ready_up = True
        self._ready = self._make_ready()

    def _make_ready(self) -> ReadyUp:
        return ReadyUp(
            self.w,
            ReadyUpConfig(
                min_players=self._config.min_players,
                max_players=self._config.max_players,
                title=content.ReadyUp.how_to_play,
                how_to_lines=content.Strike.ready_how_to,
                pose_stills=_still_paths(),
                hold_frames=max(1, 10),
                fist_hold_frames=max(1, int(round(30 * 0.5))),
                forget_frames=30,
                debug=self._config.debug,
            ),
        )

    @property
    def gesture_hands(self) -> int:
        if self._in_ready_up:
            return self._config.max_players * 2
        return NAV_GESTURE_HANDS

    @property
    def wants_gestures(self) -> bool:
        if self._in_ready_up:
            return True
        return isinstance(self._screen, ResultsScreen) and self._screen.idle

    def reset(self) -> None:
        library = load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._confirm = False
        self._thumb.reset()
        self.gesture_snapshot = None
        self._in_ready_up = True
        self._ready = self._make_ready()
        self._screen = LobbyScreen(
            markers=(),
            can_start=False,
            min_players=self._config.min_players,
            max_players=self._config.max_players,
        )

    def handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            if self._in_ready_up:
                if self._config.debug:
                    started = self._ready.force_start()
                    if started is not None:
                        self._begin_from_started(started, timestamp=0.0)
                return
            if isinstance(self._screen, ResultsScreen):
                return
            self._confirm = True

    def _begin_from_started(self, started: Started, timestamp: float) -> None:
        people = []
        for entry in started.roster:
            if isinstance(entry, CocoPerson):
                people.append(from_coco_person(entry))
            else:
                # Already a library Person
                people.append(entry)  # type: ignore[arg-type]
        self._in_ready_up = False
        self._screen = self._logic.step(timestamp, confirm=True, people=people)

    def update(self, frame: PoseFrame) -> None:
        self._image = frame.image

        if self._in_ready_up:
            snap = self.gesture_snapshot
            hands = snap.hands if snap is not None else ()
            started = self._ready.update(frame.people, hands)
            if started is not None:
                self._begin_from_started(started, frame.timestamp)
            return

        confirm = self._confirm
        self._confirm = False

        if isinstance(self._screen, ResultsScreen):
            confirm = False
            if self._screen.idle:
                if self._thumb.update(
                    self.gesture_snapshot,
                    frame.timestamp,
                    frame_size=(self.w, self.h),
                ):
                    confirm = True
            else:
                self._thumb.reset()
        else:
            self._thumb.reset()

        now = frame.timestamp
        people = None
        if self._logic.wants_people(now):
            people = [from_coco_person(person) for person in frame.people]
        self._screen = self._logic.step(now, confirm, frame.image, people)
        if isinstance(self._screen, LobbyScreen):
            self._in_ready_up = True
            self._ready = self._make_ready()

    def render_camera(self, image):
        source = self._image if self._image is not None else image
        if self._in_ready_up:
            composed = source
        else:
            composed = compose(self._screen, source)
            if isinstance(self._screen, ResultsScreen) and self._screen.idle:
                fh, fw = source.shape[:2]
                overlay_results_hold(
                    composed,
                    self._thumb.progress,
                    final_round=self._screen.round_number == self._screen.total_rounds,
                    snap=self.gesture_snapshot,
                    frame_size=(fw, fh),
                    players=self._screen.players,
                )
        if composed.shape[1] != self.w or composed.shape[0] != self.h:
            composed = cv2.resize(composed, (self.w, self.h))
        return composed

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        if self._in_ready_up:
            draw_ready_up(canvas, self._ready, theme=styles.STRIKE)

    def poll_nav(self):
        return None

    def debug_lines(self) -> list[str]:
        if self._in_ready_up:
            return [
                f"Ready-up: {self._ready.ready_count} ready / "
                f"{len(self._ready.eligible)} eligible"
            ]
        return [type(self._screen).__name__]
