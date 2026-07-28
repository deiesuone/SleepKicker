"""ボイスチャンネルへの参加・退出と、発話検知ソースの有効化。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, voice_recv

from bot.receive.activity_sink import ActivitySink

if TYPE_CHECKING:
    from bot.client import SleepKickerBot

log = logging.getLogger(__name__)

_CONNECT_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_SECONDS = 1.5
_POST_DISCONNECT_DELAY_SECONDS = 0.6
_CONNECT_TIMEOUT_SECONDS = 20.0


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
        self._guild_locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        """ギルドごとのボイス接続ロックを返す。"""
        lock = self._guild_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._guild_locks[guild_id] = lock
        return lock

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ログイン後、各ギルドの既存 VC を走査して監視を開始する。"""
        configured = self.bot.config.priority_voice_channel_ids
        log.info(
            "Logged in as %s — scanning existing voice channels "
            "(mode=%s threshold=%s monitor=%s)",
            self.bot.user,
            self.bot.config.detect_mode,
            self.bot.config.opus_volume_threshold,
            ",".join(str(i) for i in configured) if configured else "all",
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
            self._forget_sink_user(before.channel.guild, member.id)
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

    def _monitor_channels(
        self, guild: discord.Guild
    ) -> list[discord.VocalGuildChannel]:
        """設定順の実効監視リスト。このサーバーに存在する Voice/Stage のみ。"""
        channels: list[discord.VocalGuildChannel] = []
        for channel_id in self.bot.config.priority_voice_channel_ids:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                channels.append(channel)
        return channels

    def _has_monitor_filter(self, guild: discord.Guild) -> bool:
        """実効監視リストが非空なら True（空なら全 VC 対象）。"""
        return bool(self._monitor_channels(guild))

    def _is_allowed(
        self, guild: discord.Guild, channel: discord.abc.Snowflake
    ) -> bool:
        """監視してよいチャンネルか。"""
        if not self._has_monitor_filter(guild):
            return True
        return any(ch.id == channel.id for ch in self._monitor_channels(guild))

    def _monitor_rank(self, guild: discord.Guild, channel_id: int) -> int | None:
        """実効リスト内の順位。小さいほど優先。リスト外またはフィルタなしは None。"""
        if not self._has_monitor_filter(guild):
            return None
        for index, channel in enumerate(self._monitor_channels(guild)):
            if channel.id == channel_id:
                return index
        return None

    def _best_occupied_monitored(
        self, guild: discord.Guild
    ) -> discord.VocalGuildChannel | None:
        """実効リスト上で人がいる最左のチャンネル。フィルタなしまたは空きなら None。"""
        if not self._has_monitor_filter(guild):
            return None
        bot_id = self.bot.user.id
        for channel in self._monitor_channels(guild):
            if _human_user_ids(channel, bot_id):
                return channel
        return None

    def _can_preempt(
        self,
        guild: discord.Guild,
        target: discord.VocalGuildChannel,
        busy: discord.VocalGuildChannel,
    ) -> bool:
        """人がいる ``busy`` から ``target`` へ移動してよいか。"""
        if not self._has_monitor_filter(guild):
            return False
        target_rank = self._monitor_rank(guild, target.id)
        busy_rank = self._monitor_rank(guild, busy.id)
        if target_rank is None or busy_rank is None:
            return False
        return target_rank < busy_rank

    def _occupied_voice_channels(
        self, guild: discord.Guild
    ) -> list[discord.VocalGuildChannel]:
        """人がいる VC のスナップショット（接続で voice state が変わる前に使う）。"""
        channels: list[discord.VocalGuildChannel] = []
        seen: set[int] = set()
        bot_id = self.bot.user.id
        for state in list(guild._voice_states.values()):
            channel = state.channel
            if channel is None or channel.id in seen:
                continue
            if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                continue
            seen.add(channel.id)
            if _human_user_ids(channel, bot_id):
                channels.append(channel)
        return channels

    def _candidate_channels(
        self, guild: discord.Guild
    ) -> list[discord.VocalGuildChannel]:
        """参加候補の占有 VC（フィルタありは実効リスト順、なしは ID 昇順）。"""
        bot_id = self.bot.user.id
        if self._has_monitor_filter(guild):
            return [
                channel
                for channel in self._monitor_channels(guild)
                if _human_user_ids(channel, bot_id)
            ]
        return sorted(self._occupied_voice_channels(guild), key=lambda c: c.id)

    async def _join_first_candidate(
        self, guild: discord.Guild, *, locked: bool
    ) -> bool:
        """占有している監視対象へ順に接続を試み、成功したら True。

        候補走査では最左への書き換えをせず、失敗した部屋を飛ばして次を試す。
        """
        for channel in self._candidate_channels(guild):
            ok = (
                await self._ensure_listening_locked(channel, prefer_best=False)
                if locked
                else await self._ensure_listening(channel, prefer_best=False)
            )
            if ok:
                return True
        return False

    async def _scan_guild(self, guild: discord.Guild) -> None:
        """ギルド起動時: 監視対象の占有 VC へ参加する。"""
        await self._join_first_candidate(guild, locked=False)

    def _forget_sink_user(self, guild: discord.Guild, user_id: int) -> None:
        """参加中 VC の ActivitySink からユーザー別デコーダを破棄する。"""
        vc = guild.voice_client
        if not isinstance(vc, voice_recv.VoiceRecvClient):
            return
        sink = vc.sink
        if isinstance(sink, ActivitySink):
            sink.forget_user(user_id)

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
        self,
        channel: discord.VocalGuildChannel,
        *,
        prefer_best: bool = True,
    ) -> bool:
        """許可されれば ``channel`` に接続する。監視中なら True。

        Args:
            prefer_best: True なら実効リスト上の最左占有 VC を優先する。
                候補走査時は False にして次候補へのフォールバックを許す。

        Returns:
            当該チャンネルを監視できていれば True。
        """
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return False

        async with self._lock_for(channel.guild.id):
            return await self._ensure_listening_locked(
                channel, prefer_best=prefer_best
            )

    async def _ensure_listening_locked(
        self,
        channel: discord.VocalGuildChannel,
        *,
        prefer_best: bool = True,
    ) -> bool:
        """ロック保持中の接続本体。"""
        guild = channel.guild
        bot_id = self.bot.user.id

        # 入室イベントなどでは最左占有へ寄せる。候補走査では渡された部屋をそのまま試す。
        if prefer_best:
            best = self._best_occupied_monitored(guild)
            if best is not None:
                channel = best

        if not self._is_allowed(guild, channel):
            log.debug(
                "Skipping connect; channel not in monitor list: %s (%s)",
                channel.name,
                channel.id,
            )
            return False

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
        if busy is not None and not self._can_preempt(guild, channel, busy):
            log.info(
                "Already monitoring %s (%s); not moving to %s (%s)",
                busy.name,
                busy.id,
                channel.name,
                channel.id,
            )
            return False

        if vc is not None:
            if busy is not None and self._can_preempt(guild, channel, busy):
                log.info(
                    "Higher-priority monitor %s (%s); leaving %s (%s)",
                    channel.name,
                    channel.id,
                    busy.name,
                    busy.id,
                )
            await vc.disconnect(force=True)
            self.bot.voice_activity.clear_guild(guild.id)
            await asyncio.sleep(_POST_DISCONNECT_DELAY_SECONDS)

        # 接続前に追跡し、ハンドシェイク中の Speaking フラグを落とさない。
        for user_id in humans:
            self.bot.voice_activity.track(user_id, guild.id, channel.id)

        connected: voice_recv.VoiceRecvClient | None = None
        last_error: BaseException | None = None
        for attempt in range(1, _CONNECT_ATTEMPTS + 1):
            # 直前の失敗で半端な voice_client が残っていれば捨てる。
            stale = guild.voice_client
            if stale is not None:
                try:
                    await stale.disconnect(force=True)
                except Exception:
                    log.debug("Ignoring error while clearing stale voice client", exc_info=True)
                await asyncio.sleep(_POST_DISCONNECT_DELAY_SECONDS)

            try:
                log.info(
                    "Connecting to voice channel: %s (%s) (attempt %s/%s)…",
                    channel.name,
                    channel.id,
                    attempt,
                    _CONNECT_ATTEMPTS,
                )
                connected = await channel.connect(
                    cls=voice_recv.VoiceRecvClient,
                    timeout=_CONNECT_TIMEOUT_SECONDS,
                )
                break
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                log.warning(
                    "Voice connect timed out for %s (%s) attempt %s/%s",
                    channel.name,
                    channel.id,
                    attempt,
                    _CONNECT_ATTEMPTS,
                )
                if attempt < _CONNECT_ATTEMPTS:
                    await asyncio.sleep(_CONNECT_RETRY_DELAY_SECONDS)
            except Exception as exc:
                last_error = exc
                log.exception("Failed to connect to voice channel: %s", channel.id)
                break

        if connected is None:
            log.error(
                "Giving up voice connect to %s (%s) after %s attempts (%s)",
                channel.name,
                channel.id,
                _CONNECT_ATTEMPTS,
                type(last_error).__name__ if last_error else "unknown",
            )
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

    async def _maybe_leave(self, channel: discord.VocalGuildChannel) -> None:
        """人間がいなくなれば VC から退出し、他の占有チャンネルへ移る。"""
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return

        async with self._lock_for(channel.guild.id):
            await self._maybe_leave_locked(channel)

    async def _maybe_leave_locked(self, channel: discord.VocalGuildChannel) -> None:
        """ロック保持中の退出本体。"""
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

        await self._join_first_candidate(guild, locked=True)


async def setup(bot: SleepKickerBot) -> None:
    """Cog を Bot に登録する（discord.py 拡張ロード用）。"""
    await bot.add_cog(VoiceGuard(bot))
