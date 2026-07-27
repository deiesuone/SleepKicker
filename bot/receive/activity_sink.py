"""Audio sink that marks users as speaking when packets arrive."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import voice_recv

if TYPE_CHECKING:
    from discord import User

    from bot.services.voice_activity import VoiceActivityService


class ActivitySink(voice_recv.AudioSink):
    """Forward per-user receive events to VoiceActivityService (opus packets only)."""

    def __init__(self, activity: VoiceActivityService) -> None:
        super().__init__()
        self._activity = activity

    def wants_opus(self) -> bool:
        return True

    def write(self, user: User | None, data: voice_recv.VoiceData) -> None:
        if user is None:
            return
        self._activity.mark_speaking(user.id)

    def cleanup(self) -> None:
        pass
