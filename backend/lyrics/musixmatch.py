import os
from typing import Optional

import httpx

from .parser import LRCLine, parse_lrc

BASE_URL = "https://api.musixmatch.com/ws/1.1"
TIMEOUT = 10.0


async def fetch_synced(
    artist: str,
    title: str,
    duration_s: int = 0,
) -> Optional[list[LRCLine]]:
    """Fetch synced lyrics from Musixmatch. Requires MUSIXMATCH_API_KEY env var."""
    api_key = os.environ.get("MUSIXMATCH_API_KEY")
    if not api_key:
        return None

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Look up track ID
            r = await client.get(
                f"{BASE_URL}/matcher.track.get",
                params={
                    "q_artist": artist,
                    "q_track": title,
                    "apikey": api_key,
                },
            )
            data = r.json()
            track = data.get("message", {}).get("body", {}).get("track", {})
            track_id = track.get("track_id")
            if not track_id:
                return None

            # Fetch subtitle (synced lyrics) — requires paid plan
            r = await client.get(
                f"{BASE_URL}/track.subtitle.get",
                params={"track_id": track_id, "apikey": api_key},
            )
            data = r.json()
            subtitle = (
                data.get("message", {})
                .get("body", {})
                .get("subtitle", {})
                .get("subtitle_body", "")
            )
            if subtitle:
                return parse_lrc(subtitle)
        except (httpx.HTTPError, KeyError, ValueError):
            pass

    return None
