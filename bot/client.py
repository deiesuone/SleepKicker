"""Bot ファクトリと setup_hook の配線。"""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord.ext import commands

from bot.config import Config
from bot.services.debug_countdown import DebugCountdownService
from bot.services.sleep_guard import SleepGuardService
from bot.services.user_preferences import UserPreferencesStore
from bot.services.voice_activity import VoiceActivityService
from bot.texts.i18n import CatalogTranslator

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent


class SleepKickerBot(commands.Bot):
    """スリープキック用 Bot。設定と各サービスを保持する。"""

    def __init__(self, config: Config) -> None:
        """設定を受け取り、Intent・サービスを初期化する。"""
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.config = config
        self.voice_activity = VoiceActivityService()
        self.user_preferences = UserPreferencesStore(
            _ROOT / "data" / "user_preferences.json"
        )
        self.sleep_guard = SleepGuardService(self)
        self.debug_countdown = DebugCountdownService(self)

    async def setup_hook(self) -> None:
        """Cog 読込と SleepGuard / デバッグカウントダウンを開始する。"""
        await self.tree.set_translator(CatalogTranslator())
        await self.load_extension("bot.cogs.voice_guard")
        await self.load_extension("bot.cogs.sleepkicker_commands")
        self.sleep_guard.start()
        self.debug_countdown.start()
        log.info("SleepKicker setup complete")

    async def close(self) -> None:
        """バックグラウンドサービスを止めてから Bot を閉じる。"""
        self.debug_countdown.stop()
        self.sleep_guard.stop()
        await super().close()


def create_bot(config: Config) -> SleepKickerBot:
    """設定から SleepKickerBot インスタンスを生成する。"""
    return SleepKickerBot(config)
