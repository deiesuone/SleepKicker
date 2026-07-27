"""音声シンク: Opus パケットと合成 Speaking start/stop（外周の近似）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import voice_recv

if TYPE_CHECKING:
    from discord import Member, User

    from bot.services.voice_activity import VoiceActivityService


class ActivitySink(voice_recv.AudioSink):
    """Opus 受信と、任意の Speaking インジケータ・ラッチ更新を行う。"""

    def __init__(
        self,
        activity: VoiceActivityService,
        *,
        track_opus: bool,
        track_speaking_indicator: bool,
    ) -> None:
        """発話追跡サービスと、有効にする検知ソースを受け取る。

        Args:
            activity: 最終発話時刻などを保持するサービス。
            track_opus: True なら Opus パケットでタイマーを更新する。
            track_speaking_indicator: True なら Speaking start/stop でラッチする。
        """
        super().__init__()
        self._activity = activity
        self._track_opus = track_opus
        self._track_speaking_indicator = track_speaking_indicator

    def wants_opus(self) -> bool:
        """Opus フレームを受け取る（PCM デコードしない）。"""
        return True

    def write(self, user: User | None, data: voice_recv.VoiceData) -> None:
        """受信フレーム。USE_OPUS 有効時のみ無音タイマーを更新する。"""
        if user is None or not self._track_opus:
            return
        # USE_OPUS: 音声パケット流入中は無音タイマーを更新する。
        self._activity.mark_speaking(user.id)

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
        """シンク破棄時の後始末（現状なし）。"""
        pass
