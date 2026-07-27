"""任意: 追跡ユーザーごとの無音カウントダウンを 1Hz でコンソール出力する。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from discord.ext import tasks

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)


class DebugCountdownService:
    """DEBUG_LOG 有効時に無音カウントダウンを表示する。"""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Bot 参照を保持する。"""
        self._bot = bot

    def start(self) -> None:
        """DEBUG_LOG が有効なら 1 秒ループを開始する。"""
        if not self._bot.config.debug_log:
            return
        self._tick.start()
        log.info("DEBUG_LOG 有効 — 無音カウントダウンを1秒ごとに表示します")

    def stop(self) -> None:
        """ループが動いていれば停止する。"""
        if self._tick.is_running():
            self._tick.cancel()

    @tasks.loop(seconds=1)
    async def _tick(self) -> None:
        """スナップショットを取り、発話中／残り／超過／除外を1行で出す。"""
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
                    speaking = f" 発話中({source}){level}"
                parts.append(f"{label}{speaking} 無効")
            elif source is not None:
                parts.append(
                    f"{label} 発話中({source}){level} 残り={remaining:.1f}秒"
                )
            elif remaining <= 0:
                parts.append(f"{label}{level} 超過={-remaining:.1f}秒（退出待ち）")
            else:
                parts.append(f"{label}{level} 残り={remaining:.1f}秒")
        log.info("デバッグ カウントダウン: %s", " | ".join(parts))

    @_tick.before_loop
    async def _before_tick(self) -> None:
        """Bot の ready まで待つ。"""
        await self._bot.wait_until_ready()

    def _user_label(self, guild_id: int, user_id: int) -> str:
        """ログ用の表示名（可能なら Member / User、だめなら ID）。"""
        guild = self._bot.get_guild(guild_id)
        if guild is not None:
            member = guild.get_member(user_id)
            if member is not None:
                return f"{member} ({user_id})"
        user = self._bot.get_user(user_id)
        if user is not None:
            return f"{user} ({user_id})"
        return f"ユーザー:{user_id}"
