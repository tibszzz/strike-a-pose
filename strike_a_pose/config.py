"""Every tunable setting for the game, in one place."""

from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent


@dataclass(frozen=True)
class Config:
    # Pose model weights. Swap for a larger model if far-away players get
    # wrong skeletons.
    model_path: Path = REPO_ROOT / "scripts" / "yolo26n-pose.pt"
    poses_dir: Path = PACKAGE_DIR / "poses"
    camera_index: int = 0

    rounds: int = 5
    countdown_seconds: float = 5.0
    min_players: int = 2
    max_players: int = 4

    # A segment scores 100 when it points the same way as the target and
    # falls in a straight line to 0 at this many degrees off. Lower is
    # stricter.
    strictness_degrees: float = 90.0

    # A joint the model reports below this confidence counts as hidden.
    joint_confidence: float = 0.5
