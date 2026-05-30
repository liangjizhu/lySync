"""
Spotify Web API player via OAuth Authorization Code + PKCE.

First run: opens browser for user authorization.
Tokens saved to ~/.config/lysync/spotify_tokens.json and auto-refreshed.
"""
import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Optional

import httpx

from .base import BasePlayer, TrackInfo

_auth_lock: Optional[asyncio.Lock] = None

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
CALLBACK_PORT = int(REDIRECT_URI.split(":")[-1].split("/")[0])

SCOPES = "user-read-playback-state user-read-currently-playing"
TOKEN_FILE = Path.home() / ".config" / "lysync" / "spotify_tokens.json"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYER_URL = "https://api.spotify.com/v1/me/player"


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── Token storage ─────────────────────────────────────────────────────────────

def _load_tokens() -> dict:
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return {}


def _save_tokens(tokens: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


# ── OAuth callback HTTP server ────────────────────────────────────────────────

def _run_callback_server() -> str:
    """Block until Spotify redirects with auth code. Returns the code."""
    code_holder: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                code_holder.append(params["code"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family:sans-serif;padding:40px;background:#111;color:#fff">
                    <h2>lySync authorized!</h2>
                    <p>You can close this tab and return to the app.</p>
                    </body></html>
                """)
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *_):
            pass  # suppress access logs

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
    server.timeout = 120  # 2 min to authorize
    while not code_holder:
        server.handle_request()
    server.server_close()
    return code_holder[0]


# ── Token exchange / refresh ──────────────────────────────────────────────────

async def _exchange_code(code: str, verifier: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code_verifier": verifier,
        })
        r.raise_for_status()
        tokens = r.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        return tokens


async def _refresh_tokens(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        })
        r.raise_for_status()
        tokens = r.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        if "refresh_token" not in tokens:
            tokens["refresh_token"] = refresh_token  # keep old if not rotated
        return tokens


# ── Auth flow entry point ─────────────────────────────────────────────────────

async def ensure_authenticated() -> str:
    """Return a valid access token, running OAuth flow if needed."""
    global _auth_lock
    if _auth_lock is None:
        _auth_lock = asyncio.Lock()
    async with _auth_lock:
        return await _ensure_authenticated_inner()


async def _ensure_authenticated_inner() -> str:
    tokens = _load_tokens()

    # Already have a valid token
    if tokens.get("access_token") and time.time() < tokens.get("expires_at", 0) - 60:
        return tokens["access_token"]

    # Refresh if we have a refresh token
    if tokens.get("refresh_token"):
        try:
            tokens = await _refresh_tokens(tokens["refresh_token"])
            _save_tokens(tokens)
            print(f"[spotify] token refreshed")
            return tokens["access_token"]
        except Exception as e:
            print(f"[spotify] refresh failed: {e} — re-authorizing")

    # Full OAuth flow
    verifier, challenge = _pkce_pair()
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    })
    auth_url = f"{AUTH_URL}?{params}"

    print(f"\n[spotify] Opening browser for authorization...")
    print(f"[spotify] If browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    # Run blocking callback server in executor
    loop = asyncio.get_event_loop()
    code = await loop.run_in_executor(None, _run_callback_server)

    tokens = await _exchange_code(code, verifier)
    _save_tokens(tokens)
    print("[spotify] authorized successfully")
    return tokens["access_token"]


# ── Player ────────────────────────────────────────────────────────────────────

class SpotifyAPIPlayer(BasePlayer):
    def __init__(self):
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    async def _get_token(self) -> str:
        if not self._token or time.time() > self._token_expiry - 60:
            self._token = await ensure_authenticated()
            tokens = _load_tokens()
            self._token_expiry = tokens.get("expires_at", time.time() + 3600)
        return self._token

    async def _get_player_state(self) -> Optional[dict]:
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            r = await client.get(
                PLAYER_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if r.status_code == 204:
                return None  # nothing playing
            if r.status_code == 401:
                self._token = None  # force re-auth next call
                return None
            if r.status_code != 200:
                return None
            return r.json()

    async def get_current_track(self) -> Optional[TrackInfo]:
        try:
            state = await self._get_player_state()
            if not state:
                return None
            item = state.get("item")
            if not item:
                return None

            artists = ", ".join(a["name"] for a in item.get("artists", []))
            album = item.get("album", {}).get("name", "")
            return TrackInfo(
                title=item.get("name", "Unknown"),
                artist=artists or "Unknown",
                album=album,
                position_ms=state.get("progress_ms", 0),
                duration_ms=item.get("duration_ms", 0),
                player_name="spotify",
            )
        except Exception as e:
            print(f"[spotify] get_current_track error: {e}")
            return None

    async def get_position_ms(self) -> int:
        try:
            state = await self._get_player_state()
            return state.get("progress_ms", 0) if state else 0
        except Exception:
            return 0

    async def watch(self, on_track_change: Callable[[Optional[TrackInfo]], None]) -> None:
        last_key: Optional[tuple] = None
        while True:
            track = await self.get_current_track()
            key = track.cache_key() if track else None
            if key != last_key:
                last_key = key
                on_track_change(track)
            await asyncio.sleep(2.0)  # Spotify rate limit: ~180 req/min
