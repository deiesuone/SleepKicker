"""Optional: print per-user silence countdown to the console at 1 Hz."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


class DebugCountdownService:
    """Show silence countdown when DEBUG_LOG is enabled."""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Keep a bot reference."""
        self._bot = bot

    def start(self) -> None:
        """Start the 1s loop when DEBUG_LOG is enabled."""
        if not self._bot.config.debug_log:
            return
        self._tick.start()
        log.info("DEBUG_LOG enabled — printing silence countdown every 1s")

    def stop(self) -> None:
        """Stop the loop if running."""
        if self._tick.is_running():
            self._tick.cancel()

    @tasks.loop(seconds=1)
    async def _tick(self) -> None:
        """Snapshot tracked users and log speaking / remaining / overdue."""
        default = self._bot.config.silence_threshold_seconds
        prefs = self._bot.user_preferences

        def resolve(user_id: int, guild_id: int) -> float | None:
            return prefs.effective_threshold_seconds(
                guild_id, user_id, default_seconds=default
            )

        rows = self._bot.voice_activity.countdown_snapshot(resolve)
        if not rows:
            return

        parts: list[str] = []
        for (
            user_id,
            guild_id,
            channel_id,
            remaining,
            source,
            opus_rms,
            gate_rms,
            exempt,
        ) in sorted(rows, key=lambda r: (not r[7], r[4] is None, r[3])):
            label = self._user_label(guild_id, user_id)
            bits: list[str] = []
            if gate_rms is not None:
                bits.append(f"gate={gate_rms:.0f}")
            bits.append(f"rms={(0.0 if opus_rms is None else opus_rms):.0f}")
            level = " " + " ".join(bits)
            if exempt:
                speaking = ""
                if source is not None:
                    speaking = f" speaking({source}){level}"
                parts.append(f"{label}{speaking} off")
            elif source is not None:
                parts.append(
                    f"{label} speaking({source}){level} remaining={remaining:.1f}s"
                )
            elif remaining <= 0:
                parts.append(
                    f"{label}{level} overdue={-remaining:.1f}s (pending disconnect)"
                )
            else:
                parts.append(f"{label}{level} remaining={remaining:.1f}s")
        log.info("debug countdown: %s", " | ".join(parts))

    @_tick.before_loop
    async def _before_tick(self) -> None:
        """Wait until the bot is ready."""
        await self._bot.wait_until_ready()

    def _user_label(self, guild_id: int, user_id: int) -> str:
        """Display name for logs (Member / User when possible, else ID)."""
        guild = self._bot.get_guild(guild_id)
        if guild is not None:
            member = guild.get_member(user_id)
            if member is not None:
                return f"{member} ({user_id})"
        user = self._bot.get_user(user_id)
        if user is not None:
            return f"{user} ({user_id})"
        return f"user:{user_id}"
