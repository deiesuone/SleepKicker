"""環境変数（python-dotenv）から設定を読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from bot.types import DetectMode

_ROOT = Path(__file__).resolve().parent.parent

_TRUE_VALUES = frozenset({"true", "1", "yes"})
_FALSE_VALUES = frozenset({"false", "0", "no"})

# .env 未設定時および .env.example と揃える既定値
DEFAULT_SILENCE_THRESHOLD_SECONDS = 3600.0
DEFAULT_CHECK_INTERVAL_SECONDS = 10.0
DEFAULT_DETECT_MODE: DetectMode = "opus"
DEFAULT_OPUS_VOLUME_THRESHOLD = 1000.0
DEFAULT_DEBUG_LOG = False


@dataclass(frozen=True, slots=True)
class Config:
    """実行時設定。

    Attributes:
        discord_token: Bot トークン。
        silence_threshold_seconds: 無音とみなす秒数（超過で退出）。個人未設定時の既定。
        check_interval_seconds: SleepGuard のポーリング間隔（秒）。
        detect_mode: 発話検知のサーバー既定（opus / speaking）。
        opus_volume_threshold: Opus 判定の PCM RMS しきい値（0 なら音量ゲートなし）。
        debug_log: 1秒ごとのカウントダウンログを出すか。
        priority_voice_channel_ids: 監視対象 VC ID（左ほど優先。空または無効のみなら全 VC）。
    """

    discord_token: str
    silence_threshold_seconds: float
    check_interval_seconds: float
    detect_mode: DetectMode
    opus_volume_threshold: float
    debug_log: bool
    # 左から右へ: 先頭ほど優先度が高い。サーバーに存在する ID だけが実効リスト。
    priority_voice_channel_ids: tuple[int, ...]


def _parse_bool(name: str, raw: str | None, *, default: bool) -> bool:
    """真偽値環境変数を解釈する。"""
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


def _parse_detect_mode(
    raw: str | None, *, default: DetectMode = DEFAULT_DETECT_MODE
) -> DetectMode:
    """USE_MODE を opus / speaking として解釈する。"""
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("opus", "speaking"):
        return value  # type: ignore[return-value]
    raise RuntimeError(
        f"USE_MODE must be opus or speaking (got {raw!r})."
    )


def _parse_positive_float(name: str, raw: str | None, *, default: float) -> float:
    """正の浮動小数（0 より大きい）を解釈する。"""
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number (got {raw!r}).") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be > 0 (got {value!r}).")
    return value


def _parse_non_negative_float(
    name: str, raw: str | None, *, default: float
) -> float:
    """0 以上の浮動小数を解釈する。"""
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number (got {raw!r}).") from exc
    if value < 0:
        raise RuntimeError(f"{name} must be >= 0 (got {value!r}).")
    return value


def _parse_snowflake_list(name: str, raw: str | None) -> tuple[int, ...]:
    """カンマ区切りの Discord スノーフレーク ID を解釈する。空なら ()。"""
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
    """プロジェクトルートの ``.env`` を読み込み Config を構築する。"""
    load_dotenv(_ROOT / ".env")

    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and set your bot token."
        )

    return Config(
        discord_token=token,
        silence_threshold_seconds=_parse_positive_float(
            "SILENCE_THRESHOLD_SECONDS",
            os.getenv("SILENCE_THRESHOLD_SECONDS"),
            default=DEFAULT_SILENCE_THRESHOLD_SECONDS,
        ),
        check_interval_seconds=_parse_positive_float(
            "CHECK_INTERVAL_SECONDS",
            os.getenv("CHECK_INTERVAL_SECONDS"),
            default=DEFAULT_CHECK_INTERVAL_SECONDS,
        ),
        detect_mode=_parse_detect_mode(
            os.getenv("USE_MODE"), default=DEFAULT_DETECT_MODE
        ),
        opus_volume_threshold=_parse_non_negative_float(
            "OPUS_VOLUME_THRESHOLD",
            os.getenv("OPUS_VOLUME_THRESHOLD"),
            default=DEFAULT_OPUS_VOLUME_THRESHOLD,
        ),
        debug_log=_parse_bool(
            "DEBUG_LOG", os.getenv("DEBUG_LOG"), default=DEFAULT_DEBUG_LOG
        ),
        priority_voice_channel_ids=_parse_snowflake_list(
            "PRIORITY_VOICE_CHANNEL_ID", os.getenv("PRIORITY_VOICE_CHANNEL_ID")
        ),
    )
