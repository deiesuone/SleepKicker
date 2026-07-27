"""Track per-user last speaking time and silence thresholds."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone


class VoiceActivityService:
    """Thread-safe map of user_id -> last spoke timestamp."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # user_id -> (guild_id, channel_id, last_spoke_at)
        self._last_spoke: dict[int, tuple[int, int, datetime]] = {}

    def track(self, user_id: int, guild_id: int, channel_id: int) -> None:
        """Register a user as present; set last spoke to now (grace on join)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._last_spoke[user_id] = (guild_id, channel_id, now)

    def untrack(self, user_id: int) -> None:
        with self._lock:
            self._last_spoke.pop(user_id, None)

    def mark_speaking(self, user_id: int) -> None:
        """Update last spoke time if the user is currently tracked."""
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._last_spoke.get(user_id)
            if entry is None:
                return
            guild_id, channel_id, _ = entry
            self._last_spoke[user_id] = (guild_id, channel_id, now)

    def silent_users(self, threshold_seconds: float) -> list[tuple[int, int, int]]:
        """Return (user_id, guild_id, channel_id) for users past the silence threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)
        with self._lock:
            return [
                (user_id, guild_id, channel_id)
                for user_id, (guild_id, channel_id, last_spoke) in self._last_spoke.items()
                if last_spoke <= cutoff
            ]

    def clear_channel(self, guild_id: int, channel_id: int) -> None:
        with self._lock:
            to_remove = [
                uid
                for uid, (gid, cid, _) in self._last_spoke.items()
                if gid == guild_id and cid == channel_id
            ]
            for uid in to_remove:
                del self._last_spoke[uid]

    def clear_guild(self, guild_id: int) -> None:
        with self._lock:
            to_remove = [
                uid for uid, (gid, _, _) in self._last_spoke.items() if gid == guild_id
            ]
            for uid in to_remove:
                del self._last_spoke[uid]
