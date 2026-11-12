"""Repo root and assets directory."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"

load_dotenv(ROOT / ".env")
