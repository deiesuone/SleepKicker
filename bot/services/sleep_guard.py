"""無音が続いたユーザーを定期的にボイスから切断する。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


class SleepGuardService:
    """無音タイムアウト監視ループ。"""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Bot 参照を保持する。"""
        self._bot = bot

    def start(self) -> None:
        """設定の間隔でチェックループを開始する。"""
        interval = self._bot.config.check_interval_seconds
        self._check.change_interval(seconds=interval)
        self._check.start()
        log.info("SleepGuard started (interval=%ss)", interval)

    def stop(self) -> None:
        """ループが動いていれば停止する。"""
        if self._check.is_running():
            self._check.cancel()

    @tasks.loop(seconds=30)
    async def _check(self) -> None:
        """しきい値超過ユーザーを切断候補として処理する。"""
        default = self._bot.config.silence_threshold_seconds
        prefs = self._bot.user_preferences

        def resolve(user_id: int, guild_id: int) -> float | None:
            return prefs.effective_threshold_seconds(
                guild_id, user_id, default_seconds=default
            )

        silent = self._bot.voice_activity.silent_users(resolve)
        if not silent:
            return

        for user_id, guild_id, channel_id in silent:
            await self._disconnect_if_still_there(user_id, guild_id, channel_id)

    @_check.before_loop
    async def _before_check(self) -> None:
        """Bot の ready まで待つ。"""
        await self._bot.wait_until_ready()

    async def _disconnect_if_still_there(
        self, user_id: int, guild_id: int, channel_id: int
    ) -> None:
        """記録どおり同じ VC にいれば切断し、追跡を外す。

        別チャンネルへ移動済みなら追跡だけ解除する（更新は voice_state 側）。
        """
        # 切断直前にもう一度除外を確認（設定変更のレース対策）。
        default = self._bot.config.silence_threshold_seconds
        if (
            self._bot.user_preferences.effective_threshold_seconds(
                guild_id, user_id, default_seconds=default
            )
            is None
        ):
            return

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
            # 別チャンネルへ移動済み。追跡の更新は voice_state ハンドラ側。
            self._bot.voice_activity.untrack(user_id)
            return

        try:
            await member.move_to(None, reason="silence timeout")
            log.info(
                "Disconnected for silence: %s (%s) channel=%s",
                member,
                user_id,
                channel_id,
            )
        except Exception:
            log.exception(
                "Failed to disconnect member: %s (%s) channel=%s",
                member,
                user_id,
                channel_id,
            )
        finally:
            self._bot.voice_activity.untrack(user_id)
