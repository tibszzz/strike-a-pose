"""Strike play path on the shared pygame shell + PoseTracker."""

from __future__ import annotations

from typing import Sequence

import cv2
import pygame

from main import content, styles
from main.nav import GestureSnapshot, ThumbHoldTracker, load_gesture_nav_config
from main.pose import PoseFrame
from main.pose.library import Pose, from_coco_person, load_library
from main.settings import StrikeConfig

from .game import compose, overlay_results_hold
from .logic import Game as StrikeLogic
from .screens import LobbyScreen, ResultsScreen, Screen


class StrikeGame:
    title = content.Strike.window_title
    background = styles.STRIKE.bg
    gesture_hands = 2

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

    @property
    def wants_gestures(self) -> bool:
        return isinstance(self._screen, ResultsScreen)

    def reset(self) -> None:
        library = load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._confirm = False
        self._thumb.reset()
        self.gesture_snapshot = None

    def handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            if isinstance(self._screen, ResultsScreen):
                return
            self._confirm = True

    def update(self, frame: PoseFrame) -> None:
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
        self._image = frame.image
        self._screen = self._logic.step(now, confirm, frame.image, people)

    def render_camera(self, image):
        source = self._image if self._image is not None else image
        composed = compose(self._screen, source)
        if isinstance(self._screen, ResultsScreen) and self._screen.idle:
            overlay_results_hold(
                composed,
                self._thumb.progress,
                final_round=self._screen.round_number == self._screen.total_rounds,
            )
        if composed.shape[1] != self.w or composed.shape[0] != self.h:
            composed = cv2.resize(composed, (self.w, self.h))
        return composed

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        return

    def poll_nav(self):
        return None

    def debug_lines(self) -> list[str]:
        return [type(self._screen).__name__]
