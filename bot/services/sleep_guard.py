"""Periodically disconnect users who have been silent too long."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


class SleepGuardService:
    def __init__(self, bot: SleepKickerBot) -> None:
        self._bot = bot

    def start(self) -> None:
        interval = self._bot.config.check_interval_seconds
        self._check.change_interval(seconds=interval)
        self._check.start()
        log.info("SleepGuard started (interval=%ss)", interval)

    def stop(self) -> None:
        if self._check.is_running():
            self._check.cancel()

    @tasks.loop(seconds=30)
    async def _check(self) -> None:
        threshold = self._bot.config.silence_threshold_seconds
        silent = self._bot.voice_activity.silent_users(threshold)
        if not silent:
            return

        for user_id, guild_id, channel_id in silent:
            await self._disconnect_if_still_there(user_id, guild_id, channel_id)

    @_check.before_loop
    async def _before_check(self) -> None:
        await self._bot.wait_until_ready()

    async def _disconnect_if_still_there(
        self, user_id: int, guild_id: int, channel_id: int
    ) -> None:
        guild = self._bot.get_guild(guild_id)
        if guild is None:
            self._bot.voice_activity.untrack(user_id)
            return

        member = guild.get_member(user_id)
        if member is None or member.bot:
            self._bot.voice_activity.untrack(user_id)
            return

        if member.voice is None or member.voice.channel is None:
            self._bot.voice_activity.untrack(user_id)
            return

        if member.voice.channel.id != channel_id:
            # Moved elsewhere; tracking will be updated by voice_state handler.
            self._bot.voice_activity.untrack(user_id)
            return

        try:
            await member.move_to(None, reason="silence timeout")
            log.info(
                "Disconnected silent member %s (%s) from channel %s",
                member,
                user_id,
                channel_id,
            )
        except Exception:
            log.exception(
                "Failed to disconnect member %s (%s) from channel %s",
                member,
                user_id,
                channel_id,
            )
        finally:
            self._bot.voice_activity.untrack(user_id)
