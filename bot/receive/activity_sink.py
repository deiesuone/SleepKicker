"""音声シンク: Opus / Speaking を受信し、ユーザー別モードで発話判定する。"""

from __future__ import annotations

import array
import math
from typing import TYPE_CHECKING

from discord.ext import voice_recv
from discord.opus import Decoder, OpusError

from bot.types import DetectMode

if TYPE_CHECKING:
    from discord import Member, User

    from bot.services.user_preferences import UserPreferencesStore
    from bot.services.voice_activity import VoiceActivityService


def _pcm_rms(pcm: bytes) -> float:
    """16-bit little-endian PCM の RMS（おおよそ 0〜32767）。"""
    if len(pcm) < 2:
        return 0.0
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    acc = 0
    for sample in samples:
        acc += sample * sample
    return math.sqrt(acc / len(samples))


class ActivitySink(voice_recv.AudioSink):
    """Opus と Speaking を常時受信し、ユーザー実効モードでタイマーを更新する。"""

    def __init__(
        self,
        activity: VoiceActivityService,
        *,
        preferences: UserPreferencesStore,
        guild_id: int,
        default_detect_mode: DetectMode,
        default_opus_volume_threshold: float,
    ) -> None:
        """発話追跡と個人設定の解決に使う依存を受け取る。"""
        super().__init__()
        self._activity = activity
        self._preferences = preferences
        self._guild_id = guild_id
        self._default_detect_mode = default_detect_mode
        self._default_opus_volume_threshold = default_opus_volume_threshold
        self._decoders: dict[int, Decoder] = {}

    def wants_opus(self) -> bool:
        """常に Opus のまま受け取り、デコードは write 内で行う。"""
        return True

    def _mode_for(self, user_id: int) -> DetectMode:
        return self._preferences.effective_detect_mode(
            self._guild_id, user_id, default=self._default_detect_mode
        )

    def _rms_threshold_for(self, user_id: int) -> float:
        return self._preferences.effective_opus_volume_threshold(
            self._guild_id,
            user_id,
            default_rms=self._default_opus_volume_threshold,
        )

    def write(self, user: User | None, data: voice_recv.VoiceData) -> None:
        """Opus モードのユーザーだけ、RMS ゲート後に無音タイマーを更新する。"""
        if user is None:
            return
        if self._mode_for(user.id) != "opus":
            return
        opus = data.opus
        if not opus:
            return

        try:
            decoder = self._decoders.get(user.id)
            if decoder is None:
                decoder = Decoder()
                self._decoders[user.id] = decoder
            pcm = decoder.decode(opus, fec=False)
        except OpusError:
            self._decoders.pop(user.id, None)
            return

        rms = _pcm_rms(pcm)
        self._activity.note_opus_rms(user.id, rms)
        threshold = self._rms_threshold_for(user.id)
        if threshold > 0 and rms < threshold:
            return
        self._activity.mark_speaking(user.id, rms=rms)

    def forget_user(self, user_id: int) -> None:
        """退出ユーザーのデコーダを破棄する。"""
        self._decoders.pop(user_id, None)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: Member | User) -> None:
        """Speaking モードのユーザーだけ発話ラッチを ON にする。"""
        if member is None:
            return
        if self._mode_for(member.id) != "speaking":
            return
        self._activity.set_speaking_flag(member.id, True)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: Member | User) -> None:
        """Speaking モードのユーザーだけ発話ラッチを OFF にする。"""
        if member is None:
            return
        if self._mode_for(member.id) != "speaking":
            return
        self._activity.set_speaking_flag(member.id, False)

    def cleanup(self) -> None:
        """ユーザー別デコーダを破棄する。"""
        self._decoders.clear()
