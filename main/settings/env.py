"""Env parsing helpers and random message pools."""

from __future__ import annotations

import dataclasses
import os
import random
from collections.abc import Sequence
from typing import TypeVar

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
    """Pick from an in-memory list; avoid an immediate repeat when there's a choice."""

    def __init__(
        self,
        items: Sequence[str],
        fallback: str,
        rng: random.Random | None = None,
    ):
        self.rng = rng or random.Random()
        cleaned = [str(item).strip() for item in items if str(item).strip()]
        self.items = cleaned if cleaned else [fallback]
        self._last: str | None = None

    def pick(self) -> str:
        options = [m for m in self.items if m != self._last] or self.items
        self._last = self.rng.choice(options)
        return self._last
