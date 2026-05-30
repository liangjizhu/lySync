from typing import Optional

from ..player.base import TrackInfo
from .parser import LRCLine
from . import lrclib, musixmatch


async def fetch(track: TrackInfo) -> Optional[list[LRCLine]]:
    """Fetch synced lyrics. Returns None if not found (STT is manual/on-demand)."""
    duration_s = track.duration_ms // 1000

    lines = await lrclib.fetch_synced(
        artist=track.artist,
        title=track.title,
        album=track.album,
        duration_s=duration_s,
    )
    if lines is not None:
        return lines

    lines = await musixmatch.fetch_synced(
        artist=track.artist,
        title=track.title,
        duration_s=duration_s,
    )
    if lines is not None:
        return lines

    return None


async def fetch_plain_hint(track: TrackInfo) -> Optional[str]:
    """Return plain lyrics text to use as Whisper transcription hint."""
    return await lrclib.fetch_plain(
        artist=track.artist,
        title=track.title,
        album=track.album,
        duration_s=track.duration_ms // 1000,
    )
