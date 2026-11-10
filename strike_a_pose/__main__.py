"""Usage: python -m strike_a_pose duel [--camera 0] [--imgsz 640] [--device mps]

Defaults come from `.env` (CAMERA, IMGSZ, DEVICE); flags override them.
"""

import argparse
import importlib

from strike_a_pose.config import env

GAMES = {
    "duel": "strike_a_pose.games.duel.game:DuelGame",
}


def main() -> None:
    camera, imgsz, device = env("CAMERA", 0), env("IMGSZ", 640), env("DEVICE", "") or None
    parser = argparse.ArgumentParser(prog="strike_a_pose", description="Body-controlled mini games")
    parser.add_argument("game", choices=sorted(GAMES))
    parser.add_argument("--camera", type=int, default=camera, help=f"camera index (default {camera})")
    parser.add_argument("--imgsz", type=int, default=imgsz, help=f"YOLO input size; lower = faster (default {imgsz})")
    parser.add_argument("--device", default=device, help="mps / cpu (default: mps if available)")
    args = parser.parse_args()

    from strike_a_pose.app import run

    module, cls = GAMES[args.game].split(":")
    game_cls = getattr(importlib.import_module(module), cls)
    run(game_cls, camera_index=args.camera, imgsz=args.imgsz, device=args.device)


if __name__ == "__main__":
    main()
