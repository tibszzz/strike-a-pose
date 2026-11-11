"""Strike play path on the shared pygame shell + PoseTracker."""

from __future__ import annotations

from typing import Sequence

import cv2
import pygame

from main.config import Config
from main.pose import PoseFrame
from main.pose.library import Pose, from_coco_person, load_library

from .game import compose
from .logic import Game as StrikeLogic
from .screens import LobbyScreen, Screen


class StrikeGame:
    title = "Strike a Pose"
    background = (0, 0, 0)

    def __init__(
        self,
        size: tuple[int, int],
        config: Config | None = None,
        poses: Sequence[Pose] | None = None,
    ) -> None:
        self.w, self.h = size
        self._config = config if config is not None else Config()
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

    def reset(self) -> None:
        library = load_library(self._config.poses_dir)
        self._logic = StrikeLogic(self._config, library)
        self._confirm = False

    def handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            self._confirm = True

    def update(self, frame: PoseFrame) -> None:
        confirm = self._confirm
        self._confirm = False
        now = frame.timestamp
        people = None
        if self._logic.wants_people(now):
            people = [from_coco_person(person) for person in frame.people]
        self._image = frame.image
        self._screen = self._logic.step(now, confirm, frame.image, people)

    def render_camera(self, image):
        source = self._image if self._image is not None else image
        composed = compose(self._screen, source)
        if composed.shape[1] != self.w or composed.shape[0] != self.h:
            composed = cv2.resize(composed, (self.w, self.h))
        return composed

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        return

    def poll_nav(self):
        return None

    def debug_lines(self) -> list[str]:
        return [type(self._screen).__name__]
