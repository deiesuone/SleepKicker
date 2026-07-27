"""ボイスチャンネルへの参加・退出と、発話検知ソースの有効化。"""

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
    """ボイス状態キャッシュから、チャンネル内ユーザー ID を返す（Members Intent 不要）。"""
    return [
        user_id
        for user_id, state in list(channel.guild._voice_states.items())
        if state.channel is not None and state.channel.id == channel.id
    ]


def _human_user_ids(channel: discord.VocalGuildChannel, bot_user_id: int) -> list[int]:
    """チャンネル内の非 Bot ユーザー ID を返す。

    特権の Server Members Intent がないと ``channel.members`` は空になりがちで、
    ``get_member`` も未キャッシュユーザーを取りこぼす。ボイス状態の ID を優先し、
    Bot と確定できる ID だけ除外する。
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
    """VC 監視の参加方針と ActivitySink の listen 開始を担当する Cog。"""

    def __init__(self, bot: SleepKickerBot) -> None:
        """Bot 参照を保持する。"""
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ログイン後、各ギルドの既存 VC を走査して監視を開始する。"""
        priority_ids = self.bot.config.priority_voice_channel_ids
        log.info(
            "Logged in as %s — scanning existing voice channels "
            "(mode=%s threshold=%s priority=%s)",
            self.bot.user,
            self.bot.config.detect_mode,
            self.bot.config.opus_volume_threshold,
            ",".join(str(i) for i in priority_ids) if priority_ids else "none",
        )
        for guild in self.bot.guilds:
            await self._scan_guild(guild)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """入退室に応じて追跡の追加・解除と VC 参加／退出を行う。"""
        if member.id == self.bot.user.id:
            return

        # 退出: 追跡解除し、空なら Bot も退出を検討。
        if before.channel is not None and before.channel != after.channel:
            self.bot.voice_activity.untrack(member.id)
            await self._maybe_leave(before.channel)

        # 入室／移動: 監視可能なら接続する。
        if after.channel is not None and before.channel != after.channel:
            log.info(
                "Voice join/move: %s -> %s (%s)",
                member,
                after.channel.name,
                after.channel.id,
            )
            await self._ensure_listening(after.channel)

    def _priority_rank(self, channel_id: int) -> int | None:
        """優先リスト内の順位。小さいほど優先。リスト外は None。"""
        ids = self.bot.config.priority_voice_channel_ids
        try:
            return ids.index(channel_id)
        except ValueError:
            return None

    def _is_priority(self, channel: discord.abc.Snowflake) -> bool:
        """チャンネルが優先リストに含まれるか。"""
        return self._priority_rank(channel.id) is not None

    def _priority_channels(
        self, guild: discord.Guild
    ) -> list[discord.VocalGuildChannel]:
        """設定順の優先チャンネル。存在しない ID はスキップ。"""
        channels: list[discord.VocalGuildChannel] = []
        for channel_id in self.bot.config.priority_voice_channel_ids:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                channels.append(channel)
        return channels

    def _best_occupied_priority(
        self, guild: discord.Guild
    ) -> discord.VocalGuildChannel | None:
        """人がいる最優先（左端）の優先チャンネル。なければ None。"""
        bot_id = self.bot.user.id
        for channel in self._priority_channels(guild):
            if _human_user_ids(channel, bot_id):
                return channel
        return None

    def _can_preempt(
        self,
        target: discord.VocalGuildChannel,
        busy: discord.VocalGuildChannel,
    ) -> bool:
        """人がいる ``busy`` から ``target`` へ移動してよいか。

        優先チャンネルは非優先より優先。優先同士では順位が小さい方が勝つ。
        """
        target_rank = self._priority_rank(target.id)
        if target_rank is None:
            return False
        busy_rank = self._priority_rank(busy.id)
        # 優先 > 非優先。優先同士は順位が小さい方が優先。
        return busy_rank is None or target_rank < busy_rank

    async def _scan_guild(self, guild: discord.Guild) -> None:
        """ギルド起動時: 優先 VC を優先し、なければ最初の占有非優先 VC へ参加。"""
        # 人がいる優先チャンネルがあればそちらを優先（設定の左から右）。
        best_priority = self._best_occupied_priority(guild)
        if best_priority is not None:
            if await self._ensure_listening(best_priority):
                return

        # 先にスナップショット: Bot 接続で guild._voice_states が変わるため。
        channels: list[discord.VocalGuildChannel] = []
        seen: set[int] = set()
        for state in list(guild._voice_states.values()):
            channel = state.channel
            if channel is None or channel.id in seen:
                continue
            seen.add(channel.id)
            channels.append(channel)

        # 最初の占有非優先チャンネルに留まる（入室音を減らすため hop しない）。
        for channel in channels:
            if self._is_priority(channel):
                continue
            if _human_user_ids(channel, self.bot.user.id):
                if await self._ensure_listening(channel):
                    return

    def _start_receive(self, vc: voice_recv.VoiceRecvClient) -> None:
        """ActivitySink で listen を開始する（未 listen 時）。"""
        if vc.is_listening():
            return
        guild = vc.guild
        if guild is None:
            return
        vc.listen(
            ActivitySink(
                self.bot.voice_activity,
                preferences=self.bot.user_preferences,
                guild_id=guild.id,
                default_detect_mode=self.bot.config.detect_mode,
                default_opus_volume_threshold=self.bot.config.opus_volume_threshold,
            )
        )

    def _occupied_elsewhere(
        self, guild: discord.Guild, target: discord.VocalGuildChannel
    ) -> discord.VocalGuildChannel | None:
        """別の占有 VC を既に監視中ならそのチャンネルを返す。"""
        vc = guild.voice_client
        if vc is None or vc.channel is None:
            return None
        if vc.channel.id == target.id:
            return None
        if not isinstance(vc.channel, (discord.VoiceChannel, discord.StageChannel)):
            return None
        if _human_user_ids(vc.channel, self.bot.user.id):
            return vc.channel
        return None

    async def _ensure_listening(
        self, channel: discord.VocalGuildChannel
    ) -> bool:
        """許可されれば ``channel`` に接続する。監視中なら True。

        Returns:
            当該チャンネルを監視できていれば True。
        """
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return False

        guild = channel.guild
        bot_id = self.bot.user.id

        # 人がいる最優先チャンネルがあれば常にそちらを優先。
        best_priority = self._best_occupied_priority(guild)
        if best_priority is not None and channel.id != best_priority.id:
            return await self._ensure_listening(best_priority)

        humans = _human_user_ids(channel, bot_id)
        if not humans:
            log.debug(
                "Skipping connect; no human users: %s (%s)",
                channel.name,
                channel.id,
            )
            return False

        vc = guild.voice_client

        if vc is not None and vc.channel is not None and vc.channel.id == channel.id:
            for user_id in humans:
                self.bot.voice_activity.ensure_tracked(user_id, guild.id, channel.id)
            if isinstance(vc, voice_recv.VoiceRecvClient):
                self._start_receive(vc)
            return True

        busy = self._occupied_elsewhere(guild, channel)
        if busy is not None and not self._can_preempt(channel, busy):
            log.info(
                "Already monitoring %s (%s); not moving to %s (%s)",
                busy.name,
                busy.id,
                channel.name,
                channel.id,
            )
            return False

        if vc is not None:
            if busy is not None and self._can_preempt(channel, busy):
                log.info(
                    "Humans in priority channel %s (%s); leaving %s (%s)",
                    channel.name,
                    channel.id,
                    busy.name,
                    busy.id,
                )
            await vc.disconnect(force=True)
            self.bot.voice_activity.clear_guild(guild.id)

        # 接続前に追跡し、ハンドシェイク中の Speaking フラグを落とさない。
        for user_id in humans:
            self.bot.voice_activity.track(user_id, guild.id, channel.id)

        try:
            log.info("Connecting to voice channel: %s (%s)…", channel.name, channel.id)
            connected = await channel.connect(cls=voice_recv.VoiceRecvClient)
        except Exception:
            log.exception("Failed to connect to voice channel: %s", channel.id)
            for user_id in humans:
                self.bot.voice_activity.untrack(user_id)
            return False

        for user_id in _human_user_ids(channel, bot_id):
            self.bot.voice_activity.track(user_id, guild.id, channel.id)

        self._start_receive(connected)
        log.info(
            "Joined: %s (%s) mode=%s opus_rms=%s",
            channel.name,
            channel.id,
            self.bot.config.detect_mode,
            self.bot.config.opus_volume_threshold,
        )
        return True

    async def _join_any_occupied(self, guild: discord.Guild) -> None:
        """空の VC 退出後、別の占有チャンネルがあれば参加する。"""
        best_priority = self._best_occupied_priority(guild)
        if best_priority is not None:
            await self._ensure_listening(best_priority)
            return

        seen: set[int] = set()
        for state in list(guild._voice_states.values()):
            channel = state.channel
            if channel is None or channel.id in seen:
                continue
            seen.add(channel.id)
            if self._is_priority(channel):
                continue
            if _human_user_ids(channel, self.bot.user.id):
                await self._ensure_listening(channel)
                return

    async def _maybe_leave(self, channel: discord.VocalGuildChannel) -> None:
        """人間がいなくなれば VC から退出し、他の占有チャンネルへ移る。"""
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
            log.info("Left empty voice channel: %s (%s)", channel.name, channel.id)
        except Exception:
            log.exception("Failed to disconnect from voice channel: %s", channel.id)
            return

        await self._join_any_occupied(guild)


async def setup(bot: SleepKickerBot) -> None:
    """Cog を Bot に登録する（discord.py 拡張ロード用）。"""
    await bot.add_cog(VoiceGuard(bot))
