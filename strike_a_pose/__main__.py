"""Usage: python -m strike_a_pose [duel|body_trace] [--camera 0] [--imgsz 640] [--device mps]"""

import argparse
import importlib

GAMES = {
    "duel": "strike_a_pose.games.duel.game:DuelGame",
    "body_trace": "strike_a_pose.games.body_trace.game:DodgeballGame",
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="strike_a_pose", description="Body-controlled mini games")
    parser.add_argument("game", choices=sorted(GAMES))
    parser.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO input size; lower = faster")
    parser.add_argument("--device", default=None, help="mps / cpu (default: mps if available)")
    args = parser.parse_args()

    from strike_a_pose.app import run

    module, cls = GAMES[args.game].split(":")
    game_cls = getattr(importlib.import_module(module), cls)
    run(game_cls, camera_index=args.camera, imgsz=args.imgsz, device=args.device)


if __name__ == "__main__":
    main()
