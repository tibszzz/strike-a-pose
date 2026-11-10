"""Usage:
  python -m main
  python -m main duel [--camera 0] [--imgsz 640] [--device mps]
  python -m main dodgeball ...
  python -m main cannonball ...
  python -m main strike [--debug]

Bare launch opens the in-window menu (pose tracker stays warm across switches).
Defaults for the shell come from `.env` (CAMERA, IMGSZ, DEVICE); flags override them.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .config import Config, env


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    camera, imgsz, device = env("CAMERA", 0), env("IMGSZ", 640), env("DEVICE", "") or None

    parser = argparse.ArgumentParser(
        prog="python -m main",
        description="Body-controlled mini games",
    )
    parser.add_argument(
        "game",
        nargs="?",
        choices=("duel", "dodgeball", "cannonball", "strike"),
        help="optional game to start; omit for the menu",
    )
    parser.add_argument("--camera", type=int, default=camera, help=f"camera index (default {camera})")
    parser.add_argument(
        "--imgsz", type=int, default=imgsz, help=f"YOLO input size; lower = faster (default {imgsz})"
    )
    parser.add_argument("--device", default=device, help="mps / cpu (default: mps if available)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="strike only: allow a solo lobby with one person in frame",
    )
    args = parser.parse_args(argv)

    strike_config = Config(min_players=1) if args.debug else Config()
    from .app import run
    from .games.registry import build_registry, make_menu

    registry = build_registry(strike_config=strike_config)
    run(
        registry=registry,
        make_menu=make_menu(registry),
        initial_game=args.game,
        camera_index=args.camera,
        imgsz=args.imgsz,
        device=args.device,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
