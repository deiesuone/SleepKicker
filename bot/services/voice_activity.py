"""ユーザーごとの最終発話時刻と無音しきい値を追跡する。"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

# Opus パケットは高頻度のため、最終パケットからこの秒数以内をデバッグ上「発話中」とする。
_OPUS_ACTIVE_GRACE_SECONDS = 0.5


class VoiceActivityService:
    """user_id → 最終発話時刻のスレッドセーフなマップ。"""

    def __init__(self) -> None:
        """内部状態を初期化する。"""
        self._lock = threading.Lock()
        # user_id -> (guild_id, channel_id, last_spoke_at)
        self._last_spoke: dict[int, tuple[int, int, datetime]] = {}
        # パケット合成 Speaking インジケータ中のユーザー。
        self._speaking_now: set[int] = set()
        # 最終 Opus パケット時刻（USE_OPUS のみ）。デバッグ「発話中(Opus)」用。
        self._opus_last: dict[int, datetime] = {}
        # 発話とみなした直近フレームの PCM RMS（デバッグ表示用）。
        self._opus_rms: dict[int, float] = {}

    def track(self, user_id: int, guild_id: int, channel_id: int) -> None:
        """ユーザーを監視対象に登録し、最終発話を現在時刻にする（入室猶予）。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._last_spoke[user_id] = (guild_id, channel_id, now)

    def untrack(self, user_id: int) -> None:
        """ユーザーの追跡と発話フラグを解除する。"""
        with self._lock:
            self._last_spoke.pop(user_id, None)
            self._speaking_now.discard(user_id)
            self._opus_last.pop(user_id, None)
            self._opus_rms.pop(user_id, None)

    def mark_speaking(self, user_id: int, *, rms: float | None = None) -> None:
        """Opus 由来の発話として最終発話時刻を更新する（追跡中のみ）。

        Args:
            user_id: 対象ユーザー。
            rms: 直近フレームの PCM RMS（デバッグ表示用。省略可）。
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._last_spoke.get(user_id)
            if entry is None:
                return
            guild_id, channel_id, _ = entry
            self._last_spoke[user_id] = (guild_id, channel_id, now)
            self._opus_last[user_id] = now
            if rms is not None:
                self._opus_rms[user_id] = rms

    def set_speaking_flag(self, user_id: int, is_speaking: bool) -> None:
        """Speaking インジケータの start/stop を記録する。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            if is_speaking:
                self._speaking_now.add(user_id)
            else:
                self._speaking_now.discard(user_id)
            entry = self._last_spoke.get(user_id)
            if entry is None:
                return
            guild_id, channel_id, _ = entry
            # start / stop の両方で最終発話を更新し、無音は stop から起算する。
            self._last_spoke[user_id] = (guild_id, channel_id, now)

    def is_speaking_now(self, user_id: int) -> bool:
        """Speaking ラッチが ON かどうか。"""
        with self._lock:
            return user_id in self._speaking_now

    def silent_users(self, threshold_seconds: float) -> list[tuple[int, int, int]]:
        """無音しきい値を超えたユーザーの (user_id, guild_id, channel_id) を返す。"""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
        with self._lock:
            return [
                (user_id, guild_id, channel_id)
                for user_id, (guild_id, channel_id, last_spoke) in self._last_spoke.items()
                if user_id not in self._speaking_now and last_spoke <= cutoff
            ]

    def countdown_snapshot(
        self, threshold_seconds: float
    ) -> list[tuple[int, int, int, float, str | None, float | None]]:
        """デバッグ用スナップショットを返す。

        Returns:
            ``(user_id, guild_id, channel_id, 切断までの秒数, source, opus_rms)``。
            ``source`` は ``None`` / ``"Speaking"`` / ``"Opus"`` / ``"Speaking,Opus"``。
            ``opus_rms`` は Opus 発話中なら直近 RMS、それ以外は None。
            Speaking ラッチ中は残り時間をしきい値満了として扱う。
            切断待ち（超過）の場合、秒数は負になり得る。
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            rows: list[tuple[int, int, int, float, str | None, float | None]] = []
            for user_id, (guild_id, channel_id, last_spoke) in self._last_spoke.items():
                sources: list[str] = []
                speaking = user_id in self._speaking_now
                if speaking:
                    sources.append("Speaking")
                opus_at = self._opus_last.get(user_id)
                opus_active = (
                    opus_at is not None
                    and (now - opus_at).total_seconds() < _OPUS_ACTIVE_GRACE_SECONDS
                )
                if opus_active:
                    sources.append("Opus")
                source = ",".join(sources) if sources else None
                opus_rms = self._opus_rms.get(user_id) if opus_active else None
                if speaking:
                    remaining = threshold_seconds
                else:
                    remaining = threshold_seconds - (now - last_spoke).total_seconds()
                rows.append((user_id, guild_id, channel_id, remaining, source, opus_rms))
            return rows

    def clear_channel(self, guild_id: int, channel_id: int) -> None:
        """指定チャンネルに紐づく追跡をすべて解除する。"""
        with self._lock:
            to_remove = [
                uid
                for uid, (gid, cid, _) in self._last_spoke.items()
                if gid == guild_id and cid == channel_id
            ]
            for uid in to_remove:
                del self._last_spoke[uid]
                self._speaking_now.discard(uid)
                self._opus_last.pop(uid, None)
                self._opus_rms.pop(uid, None)

    def clear_guild(self, guild_id: int) -> None:
        """指定ギルドに紐づく追跡をすべて解除する。"""
        with self._lock:
            to_remove = [
                uid for uid, (gid, _) in self._last_spoke.items() if gid == guild_id
            ]
            for uid in to_remove:
                del self._last_spoke[uid]
                self._speaking_now.discard(uid)
                self._opus_last.pop(uid, None)
                self._opus_rms.pop(uid, None)
