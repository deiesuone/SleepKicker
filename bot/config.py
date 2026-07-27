"""環境変数（python-dotenv）から設定を読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent

_TRUE_VALUES = frozenset({"true", "1", "yes"})
_FALSE_VALUES = frozenset({"false", "0", "no"})


@dataclass(frozen=True, slots=True)
class Config:
    """実行時設定。

    Attributes:
        discord_token: Bot トークン。
        silence_threshold_seconds: 無音とみなす秒数（超過で切断）。
        check_interval_seconds: SleepGuard のポーリング間隔（秒）。
        use_speaking: Speaking start/stop で発話判定するか。
        use_opus: Opus 由来の音声で発話判定するか。
        opus_volume_threshold: Opus 判定の PCM RMS しきい値（0 ならパケット有無のみ）。
        debug_log: 1秒ごとのカウントダウンログを出すか。
        priority_voice_channel_ids: 優先 VC ID（左ほど優先度が高い）。
    """

    discord_token: str
    silence_threshold_seconds: float
    check_interval_seconds: float
    use_speaking: bool
    use_opus: bool
    opus_volume_threshold: float
    debug_log: bool
    # 左から右へ: 先頭ほど優先度が高い。
    priority_voice_channel_ids: tuple[int, ...]


def _parse_bool(name: str, raw: str | None, *, default: bool) -> bool:
    """真偽値環境変数を解釈する。

    Args:
        name: 環境変数名（エラーメッセージ用）。
        raw: 生の文字列。None / 空なら default。
        default: 未設定時の既定値。

    Returns:
        解釈した真偽値。

    Raises:
        RuntimeError: 解釈できない値のとき。
    """
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise RuntimeError(
        f"{name} must be one of true/false/1/0/yes/no (got {raw!r})."
    )


def _parse_snowflake_list(name: str, raw: str | None) -> tuple[int, ...]:
    """カンマ区切りの Discord スノーフレーク ID を解釈する。空なら ()。

    Args:
        name: 環境変数名（エラーメッセージ用）。
        raw: 生の文字列。

    Returns:
        ID のタプル。

    Raises:
        RuntimeError: 数値以外が含まれるとき。
    """
    if raw is None or raw.strip() == "":
        return ()
    ids: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if value == "":
            continue
        if not value.isdigit():
            raise RuntimeError(
                f"{name} must be comma-separated numeric channel IDs (got {raw!r})."
            )
        ids.append(int(value))
    return tuple(ids)


def load_config() -> Config:
    """プロジェクトルートの ``.env`` を読み込み Config を構築する。

    Returns:
        検証済みの Config。

    Raises:
        RuntimeError: 必須項目欠落、または USE_SPEAKING / USE_OPUS が両方 false。
    """
    load_dotenv(_ROOT / ".env")

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and set your bot token."
        )

    use_speaking = _parse_bool(
        "USE_SPEAKING", os.getenv("USE_SPEAKING"), default=False
    )
    use_opus = _parse_bool("USE_OPUS", os.getenv("USE_OPUS"), default=True)

    if not use_speaking and not use_opus:
        raise RuntimeError(
            "At least one of USE_SPEAKING or USE_OPUS must be true."
        )

    opus_volume_threshold = float(os.getenv("OPUS_VOLUME_THRESHOLD", "0"))
    if opus_volume_threshold < 0:
        raise RuntimeError(
            f"OPUS_VOLUME_THRESHOLD must be >= 0 (got {opus_volume_threshold!r})."
        )

    return Config(
        discord_token=token,
        silence_threshold_seconds=float(os.getenv("SILENCE_THRESHOLD_SECONDS", "600")),
        check_interval_seconds=float(os.getenv("CHECK_INTERVAL_SECONDS", "30")),
        use_speaking=use_speaking,
        use_opus=use_opus,
        opus_volume_threshold=opus_volume_threshold,
        debug_log=_parse_bool("DEBUG_LOG", os.getenv("DEBUG_LOG"), default=False),
        priority_voice_channel_ids=_parse_snowflake_list(
            "PRIORITY_VOICE_CHANNEL_ID", os.getenv("PRIORITY_VOICE_CHANNEL_ID")
        ),
    )
