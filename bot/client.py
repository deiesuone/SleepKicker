"""Bot factory and setup_hook wiring."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import Config
from bot.services.sleep_guard import SleepGuardService
from bot.services.voice_activity import VoiceActivityService

log = logging.getLogger(__name__)


class SleepKickerBot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.config = config
        self.voice_activity = VoiceActivityService()
        self.sleep_guard = SleepGuardService(self)

    async def setup_hook(self) -> None:
        await self.load_extension("bot.cogs.voice_guard")
        self.sleep_guard.start()
        log.info("SleepKicker setup complete")

    async def close(self) -> None:
        self.sleep_guard.stop()
        await super().close()


def create_bot(config: Config) -> SleepKickerBot:
    return SleepKickerBot(config)
