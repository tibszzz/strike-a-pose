"""Tunable settings for the Strike a Pose party game."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import ASSETS


@dataclass(frozen=True)
class StrikeConfig:
    # Pose model weights. Swap for a larger model if far-away players get
    # wrong skeletons.
    model_path: Path = ASSETS / "models" / "yolo26n-pose.pt"
    poses_dir: Path = ASSETS / "poses"
    camera_index: int = 0

    rounds: int = 5
    countdown_seconds: float = 5.0
    # Dramatic score reveal on ResultsScreen: post-snapshot beat, then scramble.
    # Thumbs-up / hand landmarks activate when the reveal locks.
    results_hold_s: float = 0.5
    results_reveal_s: float = 2.0
    results_reveal_hz: float = 20.0
    min_players: int = 2
    max_players: int = 4

    # Solo lobby + pad results to max_players so reveal timing can be tested alone.
    debug: bool = False

    # A segment scores 100 when it points the same way as the target and
    # falls in a straight line to 0 at this many degrees off. Lower is
    # stricter.
    strictness_degrees: float = 50.0

    # A joint the model reports below this confidence counts as hidden.
    joint_confidence: float = 0.5
