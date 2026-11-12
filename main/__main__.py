"""Usage:
  python -m main
  python -m main duel [--camera 0] [--imgsz 640] [--device mps] [--debug]
  python -m main dodgeball ...
  python -m main [--debug]
  python -m main strike [--debug]

Bare launch opens the in-window menu (pose tracker stays warm
across switches). Defaults for the shell come from `.env` (CAMERA, CAM_WIDTH,
CAM_HEIGHT, IMGSZ, DEVICE, FULLSCREEN); flags override them.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from typing import Sequence

from .config import Config, env, from_env
from .settings import DodgeballConfig, DuelConfig


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    camera = env("CAMERA", 0)
    cam_width = env("CAM_WIDTH", 1920)
    cam_height = env("CAM_HEIGHT", 1080)
    imgsz = env("IMGSZ", 640)
    device = env("DEVICE", "") or None
    fullscreen = env("FULLSCREEN", 1) != 0

    parser = argparse.ArgumentParser(
        prog="python -m main",
        description="Body-controlled mini games",
    )
    parser.add_argument(
        "game",
        nargs="?",
        choices=("duel", "dodgeball", "strike"),
        help="optional game to start; omit for the menu",
    )
    parser.add_argument("--camera", type=int, default=camera, help=f"camera index (default {camera})")
    parser.add_argument(
        "--width",
        type=int,
        default=cam_width,
        help=f"requested camera width (default {cam_width})",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=cam_height,
        help=f"requested camera height (default {cam_height})",
    )
    parser.add_argument(
        "--imgsz", type=int, default=imgsz, help=f"YOLO input size; lower = faster (default {imgsz})"
    )
    parser.add_argument("--device", default=device, help="mps / cpu (default: mps if available)")
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="start in a window instead of fullscreen (F still toggles)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="keyboard menu nav; solo play for all games; duel idle ghost opponent",
    )
    args = parser.parse_args(argv)

    # debug=True: ReadyUp / strike lobby accept one player; duel fills the empty half.
    strike_config = Config(debug=True) if args.debug else Config()
    duel_config = from_env(DuelConfig)
    dodgeball_config = DodgeballConfig(debug=True) if args.debug else DodgeballConfig()
    if args.debug:
        duel_config = replace(duel_config, debug=True)
    from .app import run
    from .games.registry import build_registry, make_how_to, make_menu

    registry = build_registry(
        strike_config=strike_config,
        duel_config=duel_config,
        dodgeball_config=dodgeball_config,
    )
    run(
        registry=registry,
        make_menu=make_menu(registry),
        make_how_to=make_how_to(registry),
        initial_game=args.game,
        camera_index=args.camera,
        camera_width=args.width,
        camera_height=args.height,
        imgsz=args.imgsz,
        device=args.device,
        debug=args.debug,
        fullscreen=False if args.windowed else fullscreen,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
