import asyncio
import json
import os
import platform
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .player.base import TrackInfo
from .lyrics import fetcher as lyrics_fetcher
from .language import detect as lang_detect, translate as lang_translate
from .sync import SyncEngine

WS_PORT = 7314

# ── State ─────────────────────────────────────────────────────────────────────

_clients: set[WebSocket] = set()
_target_lang: str = "en"
_translation_provider: str = "google"
_current_track: Optional[TrackInfo] = None
_sync_engine: Optional[SyncEngine] = None


async def _broadcast(message: dict) -> None:
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


def _make_player():
    # Use Spotify Web API if credentials are configured
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET"):
        from .player.spotify_api import SpotifyAPIPlayer
        return SpotifyAPIPlayer()
    if platform.system() == "Windows":
        from .player.windows import WindowsPlayer
        return WindowsPlayer()
    from .player.linux import LinuxPlayer
    return LinuxPlayer()


async def _on_track_change(track: Optional[TrackInfo]) -> None:
    global _current_track
    _current_track = track

    if track is None:
        await _broadcast({"type": "track_changed", "payload": None})
        _sync_engine.update_track(None)
        return

    print(f"[track] {track.artist} — {track.title} @ {track.position_ms}ms")
    await _broadcast({"type": "track_changed", "payload": asdict(track)})
    _sync_engine.update_track(track)

    # Fetch lyrics asynchronously
    print(f"[lyrics] fetching...")
    lines = await lyrics_fetcher.fetch(track)
    if lines is None:
        print(f"[lyrics] not found")
        await _broadcast({"type": "lyrics_loaded", "payload": {"lines": [], "lang": None}})
        return
    print(f"[lyrics] loaded {len(lines)} lines")

    # Language detection
    texts = [l.text for l in lines if l.text]
    detected_lang = lang_detect.detect(texts) or "und"

    # Translation
    if detected_lang != _target_lang and _target_lang and lines:
        translated = lang_translate.translate_lines(
            texts, detected_lang, _target_lang, _translation_provider
        )
        for i, line in enumerate(lines):
            if i < len(translated):
                line.translated_text = translated[i]

    _sync_engine.set_lyrics(lines)

    payload_lines = [
        {"time_ms": l.time_ms, "text": l.text, "translated_text": l.translated_text}
        for l in lines
    ]
    await _broadcast({
        "type": "lyrics_loaded",
        "payload": {"lines": payload_lines, "lang": detected_lang},
    })


async def _handle_client_message(msg: dict) -> None:
    global _target_lang, _translation_provider
    msg_type = msg.get("type")

    if msg_type == "set_target_lang":
        _target_lang = msg["payload"]["lang"]
        # Re-trigger translation on current track
        if _current_track:
            await _on_track_change(_current_track)

    elif msg_type == "set_translation_provider":
        _translation_provider = msg["payload"]["provider"]


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_engine

    player = _make_player()
    _sync_engine = SyncEngine(player)
    _sync_engine.set_broadcaster(_broadcast)

    # Start sync polling loop
    sync_task = asyncio.create_task(_sync_engine.run())

    # Start player watch loop (calls _on_track_change on track switch)
    async def _watch_wrapper():
        await player.watch(lambda t: asyncio.create_task(_on_track_change(t)))

    watch_task = asyncio.create_task(_watch_wrapper())

    # Seed initial track
    initial = await player.get_current_track()
    if initial:
        await _on_track_change(initial)

    yield

    sync_task.cancel()
    watch_task.cancel()


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)

    # Send current state to newly connected client
    if _current_track:
        from dataclasses import asdict
        await websocket.send_text(json.dumps({
            "type": "track_changed",
            "payload": asdict(_current_track),
        }))

    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
                await _handle_client_message(msg)
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
