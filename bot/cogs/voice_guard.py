"""Join/leave voice channels and start listening for speaking activity."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, voice_recv

from bot.receive.activity_sink import ActivitySink

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


def _voice_user_ids(channel: discord.VocalGuildChannel) -> list[int]:
    """User IDs in the channel from voice state cache (works without members intent)."""
    return [
        user_id
        for user_id, state in list(channel.guild._voice_states.items())
        if state.channel is not None and state.channel.id == channel.id
    ]


def _human_user_ids(channel: discord.VocalGuildChannel, bot_user_id: int) -> list[int]:
    """Non-bot user IDs in the channel.

    Without the privileged Server Members Intent, ``channel.members`` is often empty
    because ``get_member`` misses uncached users. Prefer voice-state IDs and only
    skip IDs we can positively identify as bots.
    """
    humans: list[int] = []
    for user_id in _voice_user_ids(channel):
        if user_id == bot_user_id:
            continue
        member = channel.guild.get_member(user_id)
        if member is not None and member.bot:
            continue
        humans.append(user_id)
    return humans


class VoiceGuard(commands.Cog):
    def __init__(self, bot: SleepKickerBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        log.info("Logged in as %s — scanning existing voice channels", self.bot.user)
        for guild in self.bot.guilds:
            await self._scan_guild(guild)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.id == self.bot.user.id:
            return

        # Left a channel: untrack and maybe leave if empty.
        if before.channel is not None and before.channel != after.channel:
            self.bot.voice_activity.untrack(member.id)
            await self._maybe_leave(before.channel)

        # Joined or moved into a channel: track and ensure bot is connected.
        if after.channel is not None and before.channel != after.channel:
            log.info(
                "Voice join/move: %s -> %s (%s)",
                member,
                after.channel.name,
                after.channel.id,
            )
            if not member.bot:
                self.bot.voice_activity.track(
                    member.id, member.guild.id, after.channel.id
                )
            await self._ensure_listening(after.channel)

    async def _scan_guild(self, guild: discord.Guild) -> None:
        # Snapshot first: connecting the bot mutates guild._voice_states.
        channels: list[discord.VocalGuildChannel] = []
        seen: set[int] = set()
        for state in list(guild._voice_states.values()):
            channel = state.channel
            if channel is None or channel.id in seen:
                continue
            seen.add(channel.id)
            channels.append(channel)

        for channel in channels:
            if _human_user_ids(channel, self.bot.user.id):
                await self._ensure_listening(channel)

    async def _ensure_listening(
        self, channel: discord.VocalGuildChannel
    ) -> None:
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return

        bot_id = self.bot.user.id
        humans = _human_user_ids(channel, bot_id)
        if not humans:
            log.debug("No humans in %s (%s); skip connect", channel.name, channel.id)
            return

        guild = channel.guild
        vc = guild.voice_client

        if vc is not None and vc.channel is not None and vc.channel.id == channel.id:
            for user_id in humans:
                self.bot.voice_activity.track(user_id, guild.id, channel.id)
            if isinstance(vc, voice_recv.VoiceRecvClient) and not vc.is_listening():
                vc.listen(ActivitySink(self.bot.voice_activity))
            return

        if vc is not None:
            await vc.disconnect(force=True)
            self.bot.voice_activity.clear_guild(guild.id)

        try:
            log.info("Connecting to voice channel %s (%s)…", channel.name, channel.id)
            connected = await channel.connect(cls=voice_recv.VoiceRecvClient)
        except Exception:
            log.exception("Failed to connect to voice channel %s", channel.id)
            return

        for user_id in _human_user_ids(channel, bot_id):
            self.bot.voice_activity.track(user_id, guild.id, channel.id)

        connected.listen(ActivitySink(self.bot.voice_activity))
        log.info("Joined and listening in %s (%s)", channel.name, channel.id)

    async def _maybe_leave(self, channel: discord.VocalGuildChannel) -> None:
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return

        if _human_user_ids(channel, self.bot.user.id):
            return

        guild = channel.guild
        vc = guild.voice_client
        if vc is None or vc.channel is None or vc.channel.id != channel.id:
            self.bot.voice_activity.clear_channel(guild.id, channel.id)
            return

        self.bot.voice_activity.clear_channel(guild.id, channel.id)
        try:
            await vc.disconnect()
            log.info("Left empty voice channel %s (%s)", channel.name, channel.id)
        except Exception:
            log.exception("Failed to disconnect from voice channel %s", channel.id)


async def setup(bot: SleepKickerBot) -> None:
    await bot.add_cog(VoiceGuard(bot))
