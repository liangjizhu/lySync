import asyncio
import time
from typing import Callable, Optional

from .base import BasePlayer, TrackInfo


class WindowsPlayer(BasePlayer):
    """Windows media player via WinRT GlobalSystemMediaTransportControls."""

    def __init__(self):
        self._pos_snapshot_ms: int = 0
        self._pos_snapshot_time: float = 0.0

    async def _get_manager(self):
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
        )
        return await Manager.request_async()

    async def get_current_track(self) -> Optional[TrackInfo]:
        try:
            manager = await self._get_manager()
            session = manager.get_current_session()
            if session is None:
                return None

            props = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()

            pos_ms = int(timeline.position.total_seconds() * 1000)
            dur_ms = int(timeline.end_time.total_seconds() * 1000)
            self._pos_snapshot_ms = pos_ms
            self._pos_snapshot_time = time.monotonic()

            # Player name from source app user model id
            player_name = ""
            try:
                player_name = session.source_app_user_model_id.split("!")[-1]
            except Exception:
                pass

            return TrackInfo(
                title=props.title or "Unknown",
                artist=props.artist or "Unknown",
                album=props.album_title or "",
                position_ms=pos_ms,
                duration_ms=dur_ms,
                player_name=player_name,
            )
        except Exception:
            return None

    async def get_position_ms(self) -> int:
        try:
            manager = await self._get_manager()
            session = manager.get_current_session()
            if session is None:
                return 0
            timeline = session.get_timeline_properties()
            pos_ms = int(timeline.position.total_seconds() * 1000)
            self._pos_snapshot_ms = pos_ms
            self._pos_snapshot_time = time.monotonic()
            return pos_ms
        except Exception:
            elapsed = (time.monotonic() - self._pos_snapshot_time) * 1000
            return self._pos_snapshot_ms + int(elapsed)

    async def watch(self, on_track_change: Callable[[Optional[TrackInfo]], None]) -> None:
        last_key: Optional[tuple] = None
        while True:
            track = await self.get_current_track()
            key = track.cache_key() if track else None
            if key != last_key:
                last_key = key
                on_track_change(track)
            await asyncio.sleep(1.0)
