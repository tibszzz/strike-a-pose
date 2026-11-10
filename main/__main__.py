"""Usage:
  python -m main duel [--camera 0] [--imgsz 640] [--device mps]
  python -m main strike [--debug]

Defaults for duel come from `.env` (CAMERA, IMGSZ, DEVICE); flags override them.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Sequence

from .config import Config, env

GAMES = {
    "duel": "main.games.duel.game:DuelGame",
}


def _run_duel(argv: Sequence[str] | None) -> int:
    camera, imgsz, device = env("CAMERA", 0), env("IMGSZ", 640), env("DEVICE", "") or None
    parser = argparse.ArgumentParser(
        prog="python -m main duel",
        description="Wild West Duel",
    )
    parser.add_argument("--camera", type=int, default=camera, help=f"camera index (default {camera})")
    parser.add_argument(
        "--imgsz", type=int, default=imgsz, help=f"YOLO input size; lower = faster (default {imgsz})"
    )
    parser.add_argument("--device", default=device, help="mps / cpu (default: mps if available)")
    args = parser.parse_args(argv)

    from .app import run

    module, cls = GAMES["duel"].split(":")
    game_cls = getattr(importlib.import_module(module), cls)
    run(game_cls, camera_index=args.camera, imgsz=args.imgsz, device=args.device)
    return 0


def _run_strike(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m main strike",
        description="A party game for 2 to 4 players sharing one webcam.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="allow a solo game with one person in frame (for development)",
    )
    args = parser.parse_args(argv)
    config = Config(min_players=1) if args.debug else Config()
    from .games.strike.run import run

    return run(config)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="python -m main",
        description="Body-controlled mini games",
    )
    parser.add_argument("game", choices=("duel", "strike"))
    args, rest = parser.parse_known_args(argv)
    if args.game == "duel":
        return _run_duel(rest)
    return _run_strike(rest)


if __name__ == "__main__":
    sys.exit(main())
