from functools import lru_cache
from typing import Optional

import httpx

from .parser import LRCLine, parse_lrc

BASE_URL = "https://lrclib.net/api"
HEADERS = {"User-Agent": "lySync/0.1 (https://github.com/liangjizhu/lySync)"}
TIMEOUT = 10.0


@lru_cache(maxsize=256)
def _cached_fetch(artist: str, title: str, album: str, duration_s: int) -> Optional[list[LRCLine]]:
    return None  # populated via async path; cache slot reserved


async def fetch_synced(
    artist: str,
    title: str,
    album: str = "",
    duration_s: int = 0,
) -> Optional[list[LRCLine]]:
    """Fetch synchronized LRC lyrics from LRCLIB. Returns None if not found."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        # Try exact match first
        params: dict = {"artist_name": artist, "track_name": title}
        if album:
            params["album_name"] = album
        if duration_s:
            params["duration"] = duration_s

        try:
            r = await client.get(f"{BASE_URL}/get", params=params)
            if r.status_code == 200:
                data = r.json()
                if data.get("instrumental"):
                    return []
                synced = data.get("syncedLyrics")
                if synced:
                    return parse_lrc(synced)
                # Plain lyrics only — return as single unsynchronized block
                plain = data.get("plainLyrics")
                if plain:
                    return [LRCLine(time_ms=0, text=plain)]
        except (httpx.HTTPError, KeyError, ValueError):
            pass

        # Fuzzy search fallback
        try:
            r = await client.get(
                f"{BASE_URL}/search",
                params={"q": f"{artist} {title}"},
            )
            if r.status_code == 200:
                results = r.json()
                for item in results[:3]:
                    synced = item.get("syncedLyrics")
                    if synced:
                        return parse_lrc(synced)
        except (httpx.HTTPError, KeyError, ValueError):
            pass

    return None
