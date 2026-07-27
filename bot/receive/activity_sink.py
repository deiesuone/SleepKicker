"""音声シンク: Opus / PCM と合成 Speaking start/stop（外周の近似）。"""

from __future__ import annotations

import array
import math
from typing import TYPE_CHECKING

from discord.ext import voice_recv
from discord.opus import Decoder, OpusError

if TYPE_CHECKING:
    from discord import Member, User

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
    """Opus / PCM 受信と、任意の Speaking インジケータ・ラッチ更新を行う。"""

    def __init__(
        self,
        activity: VoiceActivityService,
        *,
        track_opus: bool,
        track_speaking_indicator: bool,
        opus_volume_threshold: float = 0.0,
    ) -> None:
        """発話追跡サービスと、有効にする検知ソースを受け取る。

        Args:
            activity: 最終発話時刻などを保持するサービス。
            track_opus: True なら Opus 由来の音声でタイマーを更新する。
            track_speaking_indicator: True なら Speaking start/stop でラッチする。
            opus_volume_threshold: PCM RMS しきい値。0 以下なら音量ゲートなし。
        """
        super().__init__()
        self._activity = activity
        self._track_opus = track_opus
        self._track_speaking_indicator = track_speaking_indicator
        self._opus_volume_threshold = opus_volume_threshold
        # ユーザー別 Opus デコーダ（壊れたフレームで状態が腐るので都度作り直す）
        self._decoders: dict[int, Decoder] = {}

    def wants_opus(self) -> bool:
        """常に Opus のまま受け取る。

        ライブラリ側 PCM デコードは ``OpusError: corrupted stream`` で
        PacketRouter 全体が落ちるため、デコードは ``write`` 内で行う。
        """
        return True

    def write(self, user: User | None, data: voice_recv.VoiceData) -> None:
        """受信フレーム。USE_OPUS 有効時のみ無音タイマーを更新する。"""
        if user is None or not self._track_opus:
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
            # DAVE 前後の壊れたフレーム等。デコーダ状態を捨てて次フレームへ。
            self._decoders.pop(user.id, None)
            return

        rms = _pcm_rms(pcm)
        if self._opus_volume_threshold > 0 and rms < self._opus_volume_threshold:
            return
        self._activity.mark_speaking(user.id, rms=rms)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_start(self, member: Member | User) -> None:
        """パケット合成の緑丸開始（Opcode 5 の speaking mode ではない）。"""
        if not self._track_speaking_indicator or member is None:
            return
        self._activity.set_speaking_flag(member.id, True)

    @voice_recv.AudioSink.listener()
    def on_voice_member_speaking_stop(self, member: Member | User) -> None:
        """パケット合成の緑丸停止（最終パケットから約 0.2 秒後）。"""
        if not self._track_speaking_indicator or member is None:
            return
        self._activity.set_speaking_flag(member.id, False)

    def cleanup(self) -> None:
        """ユーザー別デコーダを破棄する。"""
        self._decoders.clear()
