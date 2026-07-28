"""任意: 追跡中ユーザーの無音カウントダウンを 1 秒ごとにコンソールへ出す。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


class DebugCountdownService:
    """``DEBUG_LOG`` 有効時に無音カウントダウンを表示する。"""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Bot 参照を保持する。"""
        self._bot = bot

    def start(self) -> None:
        """``DEBUG_LOG`` が有効なら 1 秒ループを開始する。"""
        if not self._bot.config.debug_log:
            return
        self._tick.start()
        log.info("DEBUG_LOG enabled — printing silence countdown every 1s")

    def stop(self) -> None:
        """ループが動いていれば停止する。"""
        if self._tick.is_running():
            self._tick.cancel()

    @tasks.loop(seconds=1)
    async def _tick(self) -> None:
        """追跡ユーザーのスナップショットをログに出す。"""
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
        """Bot の ready まで待つ。"""
        await self._bot.wait_until_ready()

    def _user_label(self, guild_id: int, user_id: int) -> str:
        """ログ用の表示名（Member / User、なければ ID）。"""
        guild = self._bot.get_guild(guild_id)
        if guild is not None:
            member = guild.get_member(user_id)
            if member is not None:
                return f"{member} ({user_id})"
        user = self._bot.get_user(user_id)
        if user is not None:
            return f"{user} ({user_id})"
        return f"user:{user_id}"
