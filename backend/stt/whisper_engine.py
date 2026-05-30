"""
STT fallback using faster-whisper.
Captures system audio loopback, transcribes 30s, returns LRCLine list.

Requires: pip install lysync-backend[stt]
Linux:    PulseAudio/PipeWire monitor device
Windows:  pip install pyaudiowpatch
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from ..lyrics.parser import LRCLine

CAPTURE_SECONDS = 30
SAMPLE_RATE = 16_000
WHISPER_MODEL = "base"


async def transcribe_current_audio() -> Optional[list[LRCLine]]:
    """Capture loopback audio and transcribe via Whisper. Returns LRCLine list or None."""
    try:
        wav_path = await asyncio.get_event_loop().run_in_executor(None, _capture_audio)
        if wav_path is None:
            return None
        lines = await asyncio.get_event_loop().run_in_executor(None, _transcribe, wav_path)
        return lines
    except Exception:
        return None


def _capture_audio() -> Optional[Path]:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    monitor_device = _find_loopback_device()
    if monitor_device is None:
        return None

    try:
        audio = sd.rec(
            int(CAPTURE_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            device=monitor_device,
            dtype="float32",
        )
        sd.wait()

        tmp = Path(tempfile.mktemp(suffix=".wav"))
        sf.write(str(tmp), audio, SAMPLE_RATE)
        return tmp
    except Exception:
        return None


def _find_loopback_device() -> Optional[int]:
    import platform
    import sounddevice as sd

    if platform.system() == "Linux":
        # Find PulseAudio/PipeWire monitor device
        for i, dev in enumerate(sd.query_devices()):
            if "monitor" in dev["name"].lower() and dev["max_input_channels"] > 0:
                return i
        return None

    if platform.system() == "Windows":
        # pyaudiowpatch WASAPI loopback
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            # Find loopback for default output
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and dev["name"] == default_out["name"]:
                    return i
            p.terminate()
        except Exception:
            pass
        return None

    return None


def _transcribe(wav_path: Path) -> list[LRCLine]:
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(wav_path),
        task="transcribe",
        vad_filter=True,
        word_timestamps=True,
    )

    # Delete audio immediately (privacy)
    try:
        wav_path.unlink()
    except Exception:
        pass

    return _segments_to_lrc(segments)


def _segments_to_lrc(segments) -> list[LRCLine]:
    lines: list[LRCLine] = []
    buffer_words: list[str] = []
    buffer_start: Optional[float] = None

    for seg in segments:
        if buffer_start is None:
            buffer_start = seg.start
        buffer_words.append(seg.text.strip())

        gap = seg.end - seg.start
        if len(buffer_words) >= 8 or gap > 2.0:
            lines.append(LRCLine(
                time_ms=int(buffer_start * 1000),
                text=" ".join(buffer_words).strip(),
            ))
            buffer_words = []
            buffer_start = None

    if buffer_words and buffer_start is not None:
        lines.append(LRCLine(
            time_ms=int(buffer_start * 1000),
            text=" ".join(buffer_words).strip(),
        ))

    return lines
