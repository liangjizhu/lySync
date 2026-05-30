import asyncio
import bisect
import time
from typing import Optional

from .player.base import BasePlayer, TrackInfo
from .lyrics.parser import LRCLine

POLL_INTERVAL = 0.25   # seconds between lyric checks
API_RESYNC_INTERVAL = 5.0  # seconds between actual API calls


class SyncEngine:
    def __init__(self, player: BasePlayer):
        self._player = player
        self._lines: list[LRCLine] = []
        self._times: list[int] = []
        self._current_index: int = -1
        self._current_track: Optional[TrackInfo] = None
        self._broadcaster = None  # set by main.py

        # Software clock for position drift
        self._pos_snapshot_ms: int = 0
        self._pos_snapshot_time: float = time.monotonic()

    def set_lyrics(self, lines: list[LRCLine]) -> None:
        self._lines = lines
        self._times = [l.time_ms for l in lines]
        self._current_index = -1

    def set_broadcaster(self, broadcaster) -> None:
        self._broadcaster = broadcaster

    def update_track(self, track: Optional[TrackInfo]) -> None:
        self._current_track = track
        self._lines = []
        self._times = []
        self._current_index = -1
        if track and track.position_ms > 0:
            self._pos_snapshot_ms = track.position_ms
            self._pos_snapshot_time = time.monotonic()

    def _find_active_index(self, pos_ms: int) -> int:
        if not self._times:
            return -1
        idx = bisect.bisect_right(self._times, pos_ms) - 1
        return max(0, idx) if self._times else -1

    def _estimated_position(self) -> int:
        elapsed = (time.monotonic() - self._pos_snapshot_time) * 1000
        return self._pos_snapshot_ms + int(elapsed)

    async def run(self) -> None:
        last_resync = 0.0
        debug_tick = 0
        while True:
            now = time.monotonic()
            if now - last_resync >= API_RESYNC_INTERVAL:
                last_resync = now  # always advance to avoid hammering
                try:
                    api_pos = await self._player.get_position_ms()
                    if api_pos > 0:
                        self._pos_snapshot_ms = api_pos
                        self._pos_snapshot_time = time.monotonic()
                        print(f"[sync] resynced position: {api_pos}ms")
                except Exception as e:
                    print(f"[sync] position resync failed: {e}")

            pos_ms = self._estimated_position()
            debug_tick += 1
            if debug_tick % 20 == 0:  # every 5s
                print(f"[sync] pos={pos_ms}ms  lines={len(self._lines)}  idx={self._current_index}")

            if self._lines:
                new_idx = self._find_active_index(pos_ms)
                if new_idx != self._current_index and new_idx >= 0:
                    self._current_index = new_idx
                    line = self._lines[new_idx]
                    print(f"[sync] line_changed → idx={new_idx}: {line.text[:40]!r}")
                    if self._broadcaster:
                        await self._broadcaster({
                            "type": "line_changed",
                            "payload": {
                                "index": new_idx,
                                "text": line.text,
                                "translated_text": line.translated_text,
                            },
                        })

            await asyncio.sleep(POLL_INTERVAL)
