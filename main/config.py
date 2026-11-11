"""Back-compat re-exports. Prefer `main.settings`, `main.content`, `main.styles`."""

from __future__ import annotations

from main.settings import (
    ASSETS,
    ROOT,
    Config,
    Messages,
    StrikeConfig,
    env,
    from_env,
)

__all__ = [
    "ASSETS",
    "ROOT",
    "Config",
    "Messages",
    "StrikeConfig",
    "env",
    "from_env",
]
