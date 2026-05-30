# lySync

Floating karaoke-style desktop overlay that syncs lyrics to whatever is playing on Spotify — with automatic language detection, translation, and an optional Whisper STT fallback for songs without synced lyrics.

![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Real-time lyric sync** — bisect-based engine with software clock compensation for drift
- **Spotify Web API** — works with Spotify Web, Desktop, and Mobile (OAuth PKCE, auto token refresh)
- **LRCLIB lyrics** — free, no API key required; Musixmatch as optional fallback
- **Language detection** — langdetect + lingua; auto-detects song language
- **Translation** — Google Translate / LibreTranslate / DeepL; SQLite cache; shows original + translation stacked
- **Whisper STT sync** — on-demand audio sync for songs without synced lyrics: restarts song, records loopback, transcribes with faster-whisper
- **Manual sync offset** — ±0.5s / ±1s buttons to fine-tune timing per song
- **Customizable overlay** — font size, lines visible, position (top/center/bottom), background dim, text colors
- **Always-on-top transparent overlay** — frameless Electron window, click-through when not hovered
- **Settings persist** — all display/translation preferences saved to localStorage

---

## Stack

| Layer | Tech |
| --- | --- |
| Backend | Python 3.12 · FastAPI · WebSocket (port 7314) |
| Music detection | Spotify Web API (OAuth PKCE) · MPRIS2/D-Bus (non-Spotify Linux players) |
| Lyrics | LRCLIB · Musixmatch (optional) · faster-whisper STT (optional) |
| Language | langdetect · lingua-language-detector · deep-translator |
| Frontend | Electron 32 · React 19 · TypeScript · framer-motion · zustand |
| Build | electron-vite · Vite 5 |

---

## Requirements

- Python 3.12+
- Node.js 20+
- Spotify Developer app with OAuth credentials (free)
- Linux: PulseAudio or PipeWire (for Whisper STT loopback capture)

---

## Setup

### 1. Clone & install backend

```bash
git clone https://github.com/liangjizhu/lySync.git
cd lySync
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Optional: Whisper STT support
pip install -e ".[stt]"
```

### 2. Configure Spotify credentials

Create a Spotify Developer app at [developer.spotify.com](https://developer.spotify.com/dashboard):

- Add redirect URI: `http://127.0.0.1:8888/callback`
- Copy Client ID and Client Secret

```bash
cp .env.example .env
# Edit .env and fill in your credentials
```

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

### 3. Install frontend

```bash
cd frontend
npm install
```

---

## Running (development)

```bash
# Terminal 1 — backend
source .venv/bin/activate
uvicorn backend.main:app --port 7314
# First run: browser opens for Spotify OAuth authorization
# Tokens saved to ~/.config/lysync/spotify_tokens.json

# Terminal 2 — Electron overlay
cd frontend
npm run dev
```

The overlay window appears on your desktop. In dev mode it has a visible dark background and frame for easy positioning.

---

## Usage

| Action | How |
| --- | --- |
| See lyrics | Play any song on Spotify — lyrics load automatically |
| Settings | Click ⚙ in top-right corner of overlay |
| Translation | Settings → Target language (choose any of 11 languages) |
| Sync offset | Settings → Display → `−1s` `−½s` `0` `+½s` `+1s` buttons |
| Audio sync | "No lyrics found" screen → click **🎙 Sync with Audio** |
| Quit | Settings → Quit lySync |

### Audio Sync (Whisper STT)

For songs that LRCLIB doesn't have synced lyrics for:

1. Install STT deps: `pip install "lysync-backend[stt]"`
2. Play the song, wait for "No lyrics found"
3. Click **🎙 Sync with Audio**
4. App restarts the song, records 30s of system audio, transcribes with Whisper
5. Synced lyrics appear — first run downloads ~150MB Whisper base model

Requires a loopback audio device (PulseAudio/PipeWire monitor on Linux, WASAPI loopback on Windows).

---

## Configuration

All display settings persist across restarts (stored in Electron localStorage):

| Setting | Options |
| --- | --- |
| Font size | 14–40px slider |
| Lines visible | 3 / 5 / 7 / 9 |
| Position | Top / Center / Bottom |
| Background dim | On / Off |
| Lyrics color | White / Yellow / Cyan / Coral / Green |
| Translation color | Gold / Gray / Cyan / Coral / White |
| Target language | EN / ES / FR / DE / PT / JA / KO / ZH / AR / RU / IT |
| Translation provider | Google / LibreTranslate / DeepL |
| Sync offset | −10s to +10s in 0.5s steps |

Optional translation providers require API keys in `.env`:

```env
DEEPL_API_KEY=
LIBRE_TRANSLATE_URL=https://libretranslate.com
LIBRE_TRANSLATE_KEY=
MUSIXMATCH_API_KEY=
```

---

## Project Structure

```text
lySync/
├── backend/
│   ├── main.py              # FastAPI app + WebSocket + lifespan
│   ├── sync.py              # Software clock sync engine (bisect, 250ms poll)
│   ├── player/
│   │   ├── base.py          # TrackInfo dataclass + BasePlayer ABC
│   │   ├── spotify_api.py   # Spotify Web API (OAuth PKCE, pause/seek/resume)
│   │   ├── linux.py         # MPRIS2 D-Bus (VLC, Rhythmbox, etc.)
│   │   └── windows.py       # WinRT SMTC
│   ├── lyrics/
│   │   ├── fetcher.py       # Orchestrates LRCLIB → Musixmatch
│   │   ├── lrclib.py        # LRCLIB API client
│   │   ├── musixmatch.py    # Musixmatch fallback
│   │   └── parser.py        # LRC [mm:ss.xx] parser, strips A2 word tags
│   ├── language/
│   │   ├── detect.py        # langdetect + lingua fallback
│   │   └── translate.py     # deep-translator, SQLite cache
│   └── stt/
│       └── whisper_engine.py # Loopback capture + faster-whisper transcription
├── frontend/
│   ├── electron/main.ts     # Electron main: transparent overlay window
│   ├── src/
│   │   ├── App.tsx
│   │   ├── store.ts         # zustand store (persisted settings)
│   │   ├── hooks/useWebSocket.ts
│   │   ├── components/
│   │   │   ├── LyricsOverlay.tsx
│   │   │   └── Settings.tsx
│   │   └── styles.css
│   └── package.json
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## WebSocket Protocol

```text
Backend → Frontend:
  { type: "track_changed",    payload: TrackInfo | null }
  { type: "lyrics_loaded",    payload: { lines: LRCLine[], lang: string } }
  { type: "line_changed",     payload: { index: number, text: string, translated_text: string } }
  { type: "audio_sync_status", payload: { status: "recording"|"transcribing"|"done"|"error", message: string } }

Frontend → Backend:
  { type: "set_target_lang",          payload: { lang: string } }
  { type: "set_translation_provider", payload: { provider: "google"|"libre"|"deepl" } }
  { type: "set_sync_offset",          payload: { offset_ms: number } }
  { type: "start_audio_sync" }
```
