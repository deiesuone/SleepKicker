"""Logging helpers: soften expected Discord voice handshake noise."""

from __future__ import annotations

import logging
import sys


class SoftenVoiceHandshakeRetryFilter(logging.Filter):
    """Downgrade expected voice handshake retries to INFO with a clearer message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "discord.voice_state":
            return True

        message = record.getMessage()
        if "Failed to connect to voice" not in message or "Retrying" not in message:
            return True

        wait = record.args[0] if record.args else "?"
        record.msg = (
            "Voice handshake failed (often transient, e.g. close 4006). "
            "Retrying in %ss…"
        )
        record.args = (wait,)
        record.levelno = logging.INFO
        record.levelname = "INFO"
        record.exc_info = None
        record.exc_text = None
        return True


def configure_logging() -> None:
    """Configure root logging and quiet noisy voice_recv INFO lines."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )

    logging.getLogger("discord.voice_state").addFilter(
        SoftenVoiceHandshakeRetryFilter()
    )

    # RTCP SR / WS seq INFO is noisy during normal receive.
    logging.getLogger("discord.ext.voice_recv.reader").setLevel(logging.WARNING)
    logging.getLogger("discord.ext.voice_recv.gateway").setLevel(logging.WARNING)
