"""Run the game: `python -m strike_a_pose`."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .app import run
from .config import Config


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
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
