"""Load configuration from environment variables via python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Config:
    discord_token: str
    silence_threshold_seconds: float
    check_interval_seconds: float


def load_config() -> Config:
    """Load `.env` from the project root and build a Config instance."""
    load_dotenv(_ROOT / ".env")

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and set your bot token."
        )

    return Config(
        discord_token=token,
        silence_threshold_seconds=float(os.getenv("SILENCE_THRESHOLD_SECONDS", "600")),
        check_interval_seconds=float(os.getenv("CHECK_INTERVAL_SECONDS", "30")),
    )
