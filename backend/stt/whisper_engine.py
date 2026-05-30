"""
On-demand STT sync using faster-whisper.

Flow:
  1. Caller seeks Spotify to 0 and starts playback
  2. capture_and_transcribe() records CAPTURE_SECONDS of loopback audio
  3. Whisper transcribes with word_timestamps=True
     (plain_lyrics passed as initial_prompt for accuracy when available)
  4. Words grouped into LRC lines by silence gaps
  5. Timestamps are song-relative (recording started at position 0)

Requires: pip install "lysync-backend[stt]"
Linux:    PulseAudio/PipeWire monitor device (*.monitor)
Windows:  pyaudiowpatch WASAPI loopback
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Callable, Optional

from ..lyrics.parser import LRCLine

CAPTURE_SECONDS = 30
SAMPLE_RATE = 16_000
WHISPER_MODEL = "base"

# Silence gap (seconds) that starts a new lyric line
LINE_GAP_S = 0.45
# Max words per line before forcing a break
MAX_WORDS_PER_LINE = 9


async def capture_and_transcribe(
    duration_s: int = CAPTURE_SECONDS,
    plain_lyrics: Optional[str] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Optional[list[LRCLine]]:
    """
    Capture loopback audio for duration_s seconds, then transcribe.
    Returns LRCLine list with song-relative timestamps (ms), or None on failure.
    """
    def _progress(msg: str) -> None:
        print(f"[stt] {msg}")
        if on_progress:
            on_progress(msg)

    loop = asyncio.get_event_loop()

    _progress(f"Recording {duration_s}s of audio...")
    wav_path = await loop.run_in_executor(
        None, _capture_audio, duration_s
    )
    if wav_path is None:
        _progress("ERROR: No loopback device found. Install PulseAudio or PipeWire.")
        return None

    _progress("Transcribing with Whisper (this may take ~15s)...")
    try:
        lines = await loop.run_in_executor(
            None, _transcribe, wav_path, plain_lyrics
        )
    except Exception as e:
        _progress(f"ERROR: Transcription failed: {e}")
        return None

    _progress(f"Done — {len(lines)} lines detected")
    return lines  # caller distinguishes None (capture fail) from [] (no speech)


def _capture_audio(duration_s: int) -> Optional[Path]:
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError:
        print("[stt] sounddevice/soundfile not installed. Run: pip install 'lysync-backend[stt]'")
        return None

    device = _find_loopback_device()
    if device is None:
        return None

    try:
        audio = sd.rec(
            int(duration_s * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            device=device,
            dtype="float32",
        )
        sd.wait()
        tmp = Path(tempfile.mktemp(suffix=".wav"))
        sf.write(str(tmp), audio, SAMPLE_RATE)
        return tmp
    except Exception as e:
        print(f"[stt] capture failed: {e}")
        return None


def _find_loopback_device() -> Optional[int]:
    import platform
    try:
        import sounddevice as sd
    except ImportError:
        return None

    if platform.system() == "Linux":
        for i, dev in enumerate(sd.query_devices()):
            name = dev["name"].lower()
            if dev["max_input_channels"] > 0 and "monitor" in name:
                print(f"[stt] loopback device: [{i}] {dev['name']}")
                return i
        print("[stt] no monitor device found — check PulseAudio/PipeWire")
        return None

    if platform.system() == "Windows":
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and dev["name"] == default_out["name"]:
                    p.terminate()
                    return i
            p.terminate()
        except Exception:
            pass
        return None

    return None


def _transcribe(wav_path: Path, plain_lyrics: Optional[str]) -> list[LRCLine]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper not installed. Run: pip install 'lysync-backend[stt]'")

    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(wav_path),
        task="transcribe",
        vad_filter=True,
        word_timestamps=True,
        initial_prompt=plain_lyrics,  # improves accuracy when lyrics text is known
    )
    segments = list(segments)  # consume generator before deleting file

    try:
        wav_path.unlink()
    except Exception:
        pass

    return _words_to_lrc(segments)


def _words_to_lrc(segments) -> list[LRCLine]:
    """Convert Whisper word-timestamped segments into LRCLine list."""
    all_words: list[tuple[float, float, str]] = []
    for seg in segments:
        words = getattr(seg, "words", None) or []
        if words:
            for w in words:
                text = w.word.strip()
                if text:
                    all_words.append((w.start, w.end, text))
        else:
            text = seg.text.strip()
            if text:
                all_words.append((seg.start, seg.end, text))

    if not all_words:
        return []

    lines: list[LRCLine] = []
    buf: list[str] = []
    buf_start = 0.0
    prev_end = 0.0

    for start, end, word in all_words:
        gap = start - prev_end
        if buf and (gap > LINE_GAP_S or len(buf) >= MAX_WORDS_PER_LINE):
            lines.append(LRCLine(time_ms=int(buf_start * 1000), text=" ".join(buf)))
            buf = []

        if not buf:
            buf_start = start
        buf.append(word)
        prev_end = end

    if buf:
        lines.append(LRCLine(time_ms=int(buf_start * 1000), text=" ".join(buf)))

    return lines
