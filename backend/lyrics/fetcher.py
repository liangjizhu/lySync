from typing import Optional

from ..player.base import TrackInfo
from .parser import LRCLine
from . import lrclib, musixmatch


async def fetch(track: TrackInfo) -> Optional[list[LRCLine]]:
    """Fetch synced lyrics for track. Returns None if all sources exhausted."""
    duration_s = track.duration_ms // 1000

    # 1. LRCLIB (free, no key)
    lines = await lrclib.fetch_synced(
        artist=track.artist,
        title=track.title,
        album=track.album,
        duration_s=duration_s,
    )
    if lines is not None:
        return lines

    # 2. Musixmatch (optional key)
    lines = await musixmatch.fetch_synced(
        artist=track.artist,
        title=track.title,
        duration_s=duration_s,
    )
    if lines is not None:
        return lines

    # 3. STT fallback — imported lazily so faster-whisper is optional
    try:
        from ..stt.whisper_engine import transcribe_current_audio
        lines = await transcribe_current_audio()
        if lines is not None:
            return lines
    except ImportError:
        pass

    return None
