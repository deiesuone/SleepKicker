"""ユーザーごとの最終発話時刻と無音しきい値を追跡する。"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

# Opus パケットは高頻度のため、直近フレームの RMS 表示用の猶予。
_OPUS_RMS_GRACE_SECONDS = 0.5
# ゲート通過表示は 1Hz デバッグ刻みに残るよう長めにする。
_OPUS_GATE_GRACE_SECONDS = 1.2

# (user_id, guild_id) -> しきい値秒。None は無音退出オフ（無効）。
ThresholdResolver = Callable[[int, int], float | None]


class VoiceActivityService:
    """user_id → 最終発話時刻のスレッドセーフなマップ。"""

    def __init__(self) -> None:
        """内部状態を初期化する。"""
        self._lock = threading.Lock()
        # user_id -> (guild_id, channel_id, last_spoke_at)
        self._last_spoke: dict[int, tuple[int, int, datetime]] = {}
        # パケット合成 Speaking インジケータ中のユーザー。
        self._speaking_now: set[int] = set()
        # 直近の Opus フレーム（閾値未満も含む。デバッグ RMS 用）。
        self._opus_rms_at: dict[int, datetime] = {}
        self._opus_rms: dict[int, float] = {}
        # 音量ゲートを通った直近時刻と、そのときの RMS。
        self._opus_gate_at: dict[int, datetime] = {}
        self._opus_gate_rms: dict[int, float] = {}

    def track(self, user_id: int, guild_id: int, channel_id: int) -> None:
        """ユーザーを監視対象に登録し、最終発話を現在時刻にする（入室猶予）。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._last_spoke[user_id] = (guild_id, channel_id, now)

    def ensure_tracked(self, user_id: int, guild_id: int, channel_id: int) -> None:
        """未追跡なら登録する。既に追跡中ならタイマーは触らずチャンネル紐づけだけ更新する。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._last_spoke.get(user_id)
            if entry is None:
                self._last_spoke[user_id] = (guild_id, channel_id, now)
                return
            _, _, last_spoke = entry
            self._last_spoke[user_id] = (guild_id, channel_id, last_spoke)

    def untrack(self, user_id: int) -> None:
        """ユーザーの追跡と発話フラグを解除する。"""
        with self._lock:
            self._last_spoke.pop(user_id, None)
            self._speaking_now.discard(user_id)
            self._opus_rms_at.pop(user_id, None)
            self._opus_rms.pop(user_id, None)
            self._opus_gate_at.pop(user_id, None)
            self._opus_gate_rms.pop(user_id, None)

    def note_opus_rms(self, user_id: int, rms: float) -> None:
        """Opus フレームの RMS を記録する（無音タイマーは更新しない）。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            if user_id not in self._last_spoke:
                return
            self._opus_rms_at[user_id] = now
            self._opus_rms[user_id] = rms

    def reset_silence_timer(self, user_id: int) -> bool:
        """追跡中ユーザーの無音タイマーをいまから起算し直す。

        Returns:
            追跡中でリセットできたとき True。未追跡なら False。
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._last_spoke.get(user_id)
            if entry is None:
                return False
            guild_id, channel_id, _ = entry
            self._last_spoke[user_id] = (guild_id, channel_id, now)
            self._speaking_now.discard(user_id)
            return True

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
            self._opus_gate_at[user_id] = now
            if rms is not None:
                self._opus_gate_rms[user_id] = rms
                self._opus_rms_at[user_id] = now
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

    def silent_users(
        self, resolve_threshold: ThresholdResolver
    ) -> list[tuple[int, int, int]]:
        """しきい値超過ユーザーの (user_id, guild_id, channel_id) を返す。

        Args:
            resolve_threshold: ``(user_id, guild_id) -> 秒数``。``None`` は除外。
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            rows: list[tuple[int, int, int]] = []
            for user_id, (guild_id, channel_id, last_spoke) in self._last_spoke.items():
                if user_id in self._speaking_now:
                    continue
                threshold = resolve_threshold(user_id, guild_id)
                if threshold is None:
                    continue
                if last_spoke <= now - timedelta(seconds=threshold):
                    rows.append((user_id, guild_id, channel_id))
            return rows

    def countdown_snapshot(
        self, resolve_threshold: ThresholdResolver
    ) -> list[tuple[int, int, int, float, str | None, float | None, float | None, bool]]:
        """デバッグ用スナップショットを返す。

        Returns:
            ``(user_id, guild_id, channel_id, 切断までの秒数, source, opus_rms, gate_rms, exempt)``。
            ``source`` は ``None`` / ``"Speaking"`` / ``"Opus"`` / ``"Speaking,Opus"``。
            ``opus_rms`` は直近フレーム、``gate_rms`` は直近のゲート通過フレーム。
            ``exempt`` が True のとき残り秒は表示用に 0。
            Speaking ラッチ中は残り時間をしきい値満了として扱う。
            切断待ち（超過）の場合、秒数は負になり得る。
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            rows: list[
                tuple[int, int, int, float, str | None, float | None, float | None, bool]
            ] = []
            for user_id, (guild_id, channel_id, last_spoke) in self._last_spoke.items():
                sources: list[str] = []
                speaking = user_id in self._speaking_now
                if speaking:
                    sources.append("Speaking")
                gate_at = self._opus_gate_at.get(user_id)
                opus_gated = (
                    gate_at is not None
                    and (now - gate_at).total_seconds() < _OPUS_GATE_GRACE_SECONDS
                )
                if opus_gated:
                    sources.append("Opus")
                source = ",".join(sources) if sources else None
                rms_at = self._opus_rms_at.get(user_id)
                rms_fresh = (
                    rms_at is not None
                    and (now - rms_at).total_seconds() < _OPUS_RMS_GRACE_SECONDS
                )
                opus_rms = self._opus_rms.get(user_id) if rms_fresh else None
                gate_rms = self._opus_gate_rms.get(user_id) if opus_gated else None

                threshold = resolve_threshold(user_id, guild_id)
                if threshold is None:
                    rows.append(
                        (
                            user_id,
                            guild_id,
                            channel_id,
                            0.0,
                            source,
                            opus_rms,
                            gate_rms,
                            True,
                        )
                    )
                    continue
                if speaking:
                    remaining = threshold
                else:
                    remaining = threshold - (now - last_spoke).total_seconds()
                rows.append(
                    (
                        user_id,
                        guild_id,
                        channel_id,
                        remaining,
                        source,
                        opus_rms,
                        gate_rms,
                        False,
                    )
                )
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
                self._opus_rms_at.pop(uid, None)
                self._opus_rms.pop(uid, None)
                self._opus_gate_at.pop(uid, None)
                self._opus_gate_rms.pop(uid, None)

    def clear_guild(self, guild_id: int) -> None:
        """指定ギルドに紐づく追跡をすべて解除する。"""
        with self._lock:
            to_remove = [
                uid for uid, (gid, _) in self._last_spoke.items() if gid == guild_id
            ]
            for uid in to_remove:
                del self._last_spoke[uid]
                self._speaking_now.discard(uid)
                self._opus_rms_at.pop(uid, None)
                self._opus_rms.pop(uid, None)
                self._opus_gate_at.pop(uid, None)
                self._opus_gate_rms.pop(uid, None)
