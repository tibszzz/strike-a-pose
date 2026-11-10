"""Run the game: `python -m strike_a_pose`."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from .camera import Camera, CameraError
from .config import Config
from .detector import PoseDetector
from .game import Game
from .pose import load_library
from .render_cv import CvRenderer
from .screens import Action


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m strike_a_pose",
        description="A party game for 2 to 4 players sharing one webcam.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="allow a solo game with one person in frame (for development)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = Config(min_players=1) if args.debug else Config()
    try:
        game = Game(config, load_library(config.poses_dir))
        detector = PoseDetector(config.model_path)
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


if __name__ == "__main__":
    sys.exit(main())
