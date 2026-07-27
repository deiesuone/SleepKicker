"""Bot ファクトリと setup_hook の配線。"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import Config
from bot.services.debug_countdown import DebugCountdownService
from bot.services.sleep_guard import SleepGuardService
from bot.services.voice_activity import VoiceActivityService

log = logging.getLogger(__name__)


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
        self.sleep_guard = SleepGuardService(self)
        self.debug_countdown = DebugCountdownService(self)

    async def setup_hook(self) -> None:
        """Cog 読込と SleepGuard / デバッグカウントダウンを開始する。"""
        await self.load_extension("bot.cogs.voice_guard")
        self.sleep_guard.start()
        self.debug_countdown.start()
        log.info("SleepKicker のセットアップが完了しました")

    async def close(self) -> None:
        """バックグラウンドサービスを止めてから Bot を閉じる。"""
        self.debug_countdown.stop()
        self.sleep_guard.stop()
        await super().close()


def create_bot(config: Config) -> SleepKickerBot:
    """設定から SleepKickerBot インスタンスを生成する。"""
    return SleepKickerBot(config)
