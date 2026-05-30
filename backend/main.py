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

from .player.base import BasePlayer, TrackInfo
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
_player: Optional[BasePlayer] = None
_audio_sync_running: bool = False


async def _broadcast(message: dict) -> None:
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


def _make_player() -> BasePlayer:
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET"):
        from .player.spotify_api import SpotifyAPIPlayer
        return SpotifyAPIPlayer()
    if platform.system() == "Windows":
        from .player.windows import WindowsPlayer
        return WindowsPlayer()
    from .player.linux import LinuxPlayer
    return LinuxPlayer()


async def _set_and_broadcast_lyrics(lines: list) -> None:
    """Translate lines if needed and broadcast lyrics_loaded."""
    texts = [l.text for l in lines if l.text]
    detected_lang = lang_detect.detect(texts) or "und"

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

    print(f"[lyrics] fetching...")
    lines = await lyrics_fetcher.fetch(track)
    if lines is None:
        print(f"[lyrics] not found")
        await _broadcast({"type": "lyrics_loaded", "payload": {"lines": [], "lang": None}})
        return
    print(f"[lyrics] loaded {len(lines)} lines")

    await _set_and_broadcast_lyrics(lines)


async def _audio_sync_flow() -> None:
    global _audio_sync_running
    if _audio_sync_running or not _current_track:
        return
    _audio_sync_running = True

    async def status(s: str, msg: str) -> None:
        print(f"[stt] [{s}] {msg}")
        await _broadcast({"type": "audio_sync_status", "payload": {"status": s, "message": msg}})

    try:
        # Pre-flight: check deps
        try:
            import sounddevice  # noqa: F401
        except ImportError:
            await status("error", "sounddevice not installed. Run: pip install 'lysync-backend[stt]'")
            return
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            await status("error", "faster-whisper not installed. Run: pip install 'lysync-backend[stt]'")
            return

        # Fetch plain lyrics as Whisper hint
        plain_hint = await lyrics_fetcher.fetch_plain_hint(_current_track)
        if plain_hint:
            print(f"[stt] plain lyrics hint available ({len(plain_hint)} chars)")

        # Seek to beginning and resume
        await status("restarting", "Seeking to start of song…")
        await _player.seek(0)
        await asyncio.sleep(0.8)
        await _player.resume()
        await asyncio.sleep(0.5)

        # Seed sync clock at position 0
        _sync_engine.update_track(_current_track)

        # Capture + transcribe
        from .stt.whisper_engine import capture_and_transcribe, CAPTURE_SECONDS

        async def _on_progress(msg: str) -> None:
            if "Recording" in msg:
                await status("recording", msg)
            elif "Transcribing" in msg:
                await status("transcribing", msg)

        await status("recording", f"Recording {CAPTURE_SECONDS}s of audio…")
        lines = await capture_and_transcribe(
            duration_s=CAPTURE_SECONDS,
            plain_lyrics=plain_hint,
            on_progress=lambda msg: asyncio.create_task(
                _broadcast({"type": "audio_sync_status",
                            "payload": {"status": "recording" if "Recording" in msg else "transcribing",
                                        "message": msg}})
            ),
        )

        if lines is None:
            await status("error", "Audio capture failed — no loopback device found. Check PulseAudio/PipeWire monitor.")
            return
        if len(lines) == 0:
            await status("error", "Whisper detected no speech. Is music actually playing through speakers?")
            return

        await status("done", f"Synced {len(lines)} lines")
        print(f"[stt] generated {len(lines)} LRC lines")
        await _set_and_broadcast_lyrics(lines)

    except Exception as e:
        print(f"[stt] audio sync error: {e}")
        await status("error", f"Error: {e}")
    finally:
        _audio_sync_running = False


async def _handle_client_message(msg: dict) -> None:
    global _target_lang, _translation_provider
    msg_type = msg.get("type")

    if msg_type == "set_target_lang":
        _target_lang = msg["payload"]["lang"]
        if _current_track:
            await _on_track_change(_current_track)

    elif msg_type == "set_translation_provider":
        _translation_provider = msg["payload"]["provider"]

    elif msg_type == "set_sync_offset":
        offset_ms = int(msg["payload"]["offset_ms"])
        _sync_engine.set_offset(offset_ms)

    elif msg_type == "start_audio_sync":
        asyncio.create_task(_audio_sync_flow())


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_engine, _player

    _player = _make_player()
    _sync_engine = SyncEngine(_player)
    _sync_engine.set_broadcaster(_broadcast)

    sync_task = asyncio.create_task(_sync_engine.run())

    async def _watch_wrapper():
        await _player.watch(lambda t: asyncio.create_task(_on_track_change(t)))

    watch_task = asyncio.create_task(_watch_wrapper())

    initial = await _player.get_current_track()
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
