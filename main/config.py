"""Shared settings: `.env` helpers for duel, plus the strike game `Config`.

Every field of a config dataclass can be overridden by an env var with the field's name
in upper case, e.g. `DuelConfig.draw_timeout` <- `DRAW_TIMEOUT=2.5`. Missing vars keep
the dataclass default.
"""

from __future__ import annotations

import dataclasses
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

load_dotenv(ROOT / ".env")

T = TypeVar("T")

_PARSERS = {"int": int, "float": float, "str": str}


def env(name: str, default, cast=None):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    cast = cast or type(default)
    try:
        return cast(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name}={raw!r} in .env is not a valid {cast.__name__}") from exc


def from_env(cls: type[T]) -> T:
    """Build a config dataclass, taking each field from its UPPER_CASE env var if set."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        cast = _PARSERS.get(f.type if isinstance(f.type, str) else f.type.__name__)
        if cast is None:
            continue
        name = f.name.upper()
        if os.environ.get(name, "").strip():
            kwargs[f.name] = env(name, f.default, cast)
    return cls(**kwargs)


class Messages:
    """One message per line in a text file; blank lines and `#` comments are ignored."""

    def __init__(self, path: Path, fallback: str, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        self.items = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
        if not self.items:
            self.items = [fallback]
        self._last: str | None = None

    def pick(self) -> str:
        """Random message, avoiding an immediate repeat when there's a choice."""
        options = [m for m in self.items if m != self._last] or self.items
        self._last = self.rng.choice(options)
        return self._last


@dataclass(frozen=True)
class Config:
    """Tunable settings for the strike party game."""

    # Pose model weights. Swap for a larger model if far-away players get
    # wrong skeletons.
    model_path: Path = ASSETS / "models" / "yolo26n-pose.pt"
    poses_dir: Path = ASSETS / "poses"
    camera_index: int = 0

    rounds: int = 5
    countdown_seconds: float = 3.0
    min_players: int = 2
    max_players: int = 4

    # A segment scores 100 when it points the same way as the target and
    # falls in a straight line to 0 at this many degrees off. Lower is
    # stricter.
    strictness_degrees: float = 50.0

    # A joint the model reports below this confidence counts as hidden.
    joint_confidence: float = 0.5
