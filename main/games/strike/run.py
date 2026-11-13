"""OpenCV shell for the strike game: camera, pose, step, draw.

Keys are read by the game view. SPACE confirms. Q quits.
"""

from __future__ import annotations

import sys
import time

from main.settings import StrikeConfig as Config
from .game import CvRenderer
from .logic import Game
from .screens import Action
from main.pose.library import load_library
from main.pose.tracker import Camera, CameraError, PoseDetector


def run(config: Config) -> int:
    try:
        game = Game(config, load_library(config.poses_dir))
        detector = PoseDetector(config.model_path, imgsz=config.imgsz)
        camera = Camera(config.camera_index)
    except (CameraError, FileNotFoundError, ValueError) as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        return 1

    renderer = CvRenderer()
    try:
        action = None
        while action is not Action.QUIT:
            frame = camera.read()
            now = time.monotonic()
            people = detector.detect(frame) if game.wants_people(now) else None
            screen = game.step(now, action is Action.CONFIRM, frame, people)
            renderer.show(screen, frame)
            action = renderer.poll_action()
    except CameraError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    finally:
        camera.release()
        renderer.close()
    return 0
