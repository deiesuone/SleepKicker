"""ログ補助: 日本語メッセージと Discord ボイス周りのノイズ抑制。"""

from __future__ import annotations

import logging
import re
import sys


class SoftenVoiceHandshakeRetryFilter(logging.Filter):
    """discord.py の想定内ハンドシェイクリトライを INFO の日本語へ落とす。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """対象メッセージならレベルと文言を書き換え、常に通過させる。"""
        if record.name != "discord.voice_state":
            return True

        message = record.getMessage()
        if "Failed to connect to voice" not in message or "Retrying" not in message:
            return True

        wait = record.args[0] if record.args else "?"
        record.msg = (
            "ハンドシェイクに失敗しました（一過性のことが多い、例: close 4006）。"
            "%s秒後に再試行します…"
        )
        record.args = (wait,)
        record.levelno = logging.INFO
        record.levelname = "INFO"
        record.exc_info = None
        record.exc_text = None
        return True


class TranslateDiscordLibraryLogFilter(logging.Filter):
    """よく出る discord.py の INFO 行を日本語に書き換える。"""

    _exact: dict[str, str] = {
        "logging in using static token": "静的トークンでログインしています",
        "Connecting to voice...": "ボイスへ接続しています…",
        "Voice connection complete.": "ボイス接続が完了しました。",
    }

    _patterns: list[tuple[re.Pattern[str], str]] = [
        (
            re.compile(
                r"^Shard ID (?P<shard>\S+) has connected to Gateway \(Session ID: (?P<sid>.+)\)\.$"
            ),
            "Shard ID {shard} が Gateway に接続しました（Session ID: {sid}）。",
        ),
        (
            re.compile(
                r"^Starting voice handshake\.\.\. \(connection attempt (?P<n>\d+)\)$"
            ),
            "ハンドシェイクを開始しています…（接続試行 {n} 回目）",
        ),
        (
            re.compile(
                r"^Voice handshake complete\. Endpoint found: (?P<endpoint>.+)$"
            ),
            "ハンドシェイクが完了しました。エンドポイント: {endpoint}",
        ),
        (
            re.compile(
                r"^The voice handshake is being terminated for Channel ID (?P<channel>\d+) \(Guild ID (?P<guild>\d+)\)$"
            ),
            "ハンドシェイクを終了します（チャンネル ID {channel} / ギルド ID {guild}）",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """一致する英語ログを日本語テンプレートへ置換する。"""
        if not record.name.startswith("discord."):
            return True

        # SoftenVoiceHandshakeRetryFilter が先に書き換え済みの場合がある。
        try:
            message = record.getMessage()
        except Exception:
            return True

        if message in self._exact:
            record.msg = self._exact[message]
            record.args = ()
            return True

        for pattern, template in self._patterns:
            match = pattern.match(message)
            if match:
                record.msg = template.format_map(match.groupdict())
                record.args = ()
                return True

        return True


def configure_logging() -> None:
    """ルートログ・discord.py 日本語化・voice_recv の抑制を設定する。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )

    voice_state = logging.getLogger("discord.voice_state")
    voice_state.addFilter(SoftenVoiceHandshakeRetryFilter())

    translate = TranslateDiscordLibraryLogFilter()
    for name in (
        "discord.client",
        "discord.gateway",
        "discord.voice_state",
    ):
        logging.getLogger(name).addFilter(translate)

    # 通常受信時の RTCP SR / WS seq などの INFO がうるさいので抑える。
    logging.getLogger("discord.ext.voice_recv.reader").setLevel(logging.WARNING)
    logging.getLogger("discord.ext.voice_recv.gateway").setLevel(logging.WARNING)
