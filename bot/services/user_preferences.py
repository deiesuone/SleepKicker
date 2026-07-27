"""ギルド内ユーザーの自己申告・無音退出設定（JSON 永続化）。"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger(__name__)

DetectMode = Literal["opus", "speaking"]

_MIN_TIMEOUT_MINUTES = 1
_MAX_TIMEOUT_MINUTES = 24 * 60
_MAX_OPUS_VOLUME = 32767


@dataclass(frozen=True, slots=True)
class UserPreference:
    """ユーザー個人の退出・検知設定。

    Attributes:
        exempt: True なら無音退出オフ（無効）。
        silence_seconds: 無音秒数。None ならサーバー既定。
        detect_mode: opus / speaking。None ならサーバー既定。
        opus_volume_threshold: Opus RMS。None ならサーバー既定。
    """

    exempt: bool = False
    silence_seconds: int | None = None
    detect_mode: DetectMode | None = None
    opus_volume_threshold: float | None = None


class UserPreferencesStore:
    """``data/user_preferences.json`` にギルド別・ユーザー別設定を保存する。"""

    def __init__(self, path: Path) -> None:
        """ストアを初期化し、既存 JSON があれば読み込む。"""
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, dict[str, Any]]] = {}
        self._load()

    @property
    def min_timeout_minutes(self) -> int:
        """許容する最短タイムアウト（分）。"""
        return _MIN_TIMEOUT_MINUTES

    @property
    def max_timeout_minutes(self) -> int:
        """許容する最長タイムアウト（分）。"""
        return _MAX_TIMEOUT_MINUTES

    def get(self, guild_id: int, user_id: int) -> UserPreference:
        """保存済み設定を返す。未設定なら既定の UserPreference。"""
        with self._lock:
            raw = self._data.get(str(guild_id), {}).get(str(user_id))
            if raw is None:
                return UserPreference()
            return self._from_raw(raw)

    def set_exempt(self, guild_id: int, user_id: int, *, exempt: bool) -> UserPreference:
        """無音退出の有効／無効を保存する（exempt=True が無効）。"""
        with self._lock:
            entry = self._ensure_entry(guild_id, user_id)
            entry["exempt"] = exempt
            pref = self._from_raw(entry)
            self._save_unlocked()
            return pref

    def set_timeout_minutes(
        self, guild_id: int, user_id: int, *, minutes: int
    ) -> UserPreference:
        """無音タイムアウト（分）を保存する。"""
        if minutes < _MIN_TIMEOUT_MINUTES or minutes > _MAX_TIMEOUT_MINUTES:
            raise ValueError(
                f"timeout must be between {_MIN_TIMEOUT_MINUTES} "
                f"and {_MAX_TIMEOUT_MINUTES} minutes"
            )
        with self._lock:
            entry = self._ensure_entry(guild_id, user_id)
            entry["silence_seconds"] = int(minutes) * 60
            pref = self._from_raw(entry)
            self._save_unlocked()
            return pref

    def set_detect_mode(
        self, guild_id: int, user_id: int, *, mode: DetectMode
    ) -> UserPreference:
        """発話検知モードを保存する。"""
        if mode not in ("opus", "speaking"):
            raise ValueError(f"mode must be opus or speaking (got {mode!r})")
        with self._lock:
            entry = self._ensure_entry(guild_id, user_id)
            entry["detect_mode"] = mode
            pref = self._from_raw(entry)
            self._save_unlocked()
            return pref

    def set_opus_volume_threshold(
        self, guild_id: int, user_id: int, *, rms: float
    ) -> UserPreference:
        """本人の Opus 音量しきい値（RMS）を保存する。"""
        if rms < 0 or rms > _MAX_OPUS_VOLUME:
            raise ValueError(f"rms must be between 0 and {_MAX_OPUS_VOLUME}")
        with self._lock:
            entry = self._ensure_entry(guild_id, user_id)
            entry["opus_volume_threshold"] = float(rms)
            pref = self._from_raw(entry)
            self._save_unlocked()
            return pref

    def reset(self, guild_id: int, user_id: int) -> None:
        """個人設定を削除し、サーバー既定に戻す。"""
        with self._lock:
            guild_key = str(guild_id)
            users = self._data.get(guild_key)
            if users is None:
                return
            users.pop(str(user_id), None)
            if not users:
                self._data.pop(guild_key, None)
            self._save_unlocked()

    def effective_threshold_seconds(
        self, guild_id: int, user_id: int, *, default_seconds: float
    ) -> float | None:
        """退出判定に使う秒数。無効なら None。"""
        pref = self.get(guild_id, user_id)
        if pref.exempt:
            return None
        if pref.silence_seconds is not None:
            return float(pref.silence_seconds)
        return float(default_seconds)

    def effective_detect_mode(
        self, guild_id: int, user_id: int, *, default: DetectMode
    ) -> DetectMode:
        """発話検知モード。未設定ならサーバー既定。"""
        pref = self.get(guild_id, user_id)
        if pref.detect_mode is not None:
            return pref.detect_mode
        return default

    def effective_opus_volume_threshold(
        self, guild_id: int, user_id: int, *, default_rms: float
    ) -> float:
        """Opus 判定に使う RMS。未設定ならサーバー既定。"""
        pref = self.get(guild_id, user_id)
        if pref.opus_volume_threshold is not None:
            return float(pref.opus_volume_threshold)
        return float(default_rms)

    def _ensure_entry(self, guild_id: int, user_id: int) -> dict[str, Any]:
        guild_key = str(guild_id)
        user_key = str(user_id)
        users = self._data.setdefault(guild_key, {})
        if user_key not in users:
            users[user_key] = {
                "exempt": False,
                "silence_seconds": None,
                "detect_mode": None,
                "opus_volume_threshold": None,
            }
        return users[user_key]

    @staticmethod
    def _from_raw(raw: dict[str, Any]) -> UserPreference:
        silence = raw.get("silence_seconds")
        mode_raw = raw.get("detect_mode")
        mode: DetectMode | None = None
        if mode_raw in ("opus", "speaking"):
            mode = mode_raw
        opus = raw.get("opus_volume_threshold")
        return UserPreference(
            exempt=bool(raw.get("exempt", False)),
            silence_seconds=int(silence) if silence is not None else None,
            detect_mode=mode,
            opus_volume_threshold=float(opus) if opus is not None else None,
        )

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            text = self._path.read_text(encoding="utf-8")
            loaded = json.loads(text) if text.strip() else {}
            if not isinstance(loaded, dict):
                raise ValueError("root must be an object")
            self._data = loaded
            log.info("Loaded user preferences: %s", self._path)
        except Exception:
            log.exception(
                "Failed to load user preferences; starting empty: %s", self._path
            )
            self._data = {}

    def _save_unlocked(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._path)
