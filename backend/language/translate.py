import os
import sqlite3
import hashlib
from pathlib import Path
from typing import Optional

CACHE_DB = Path.home() / ".config" / "lysync" / "cache.db"

PROVIDERS = ["google", "libre", "deepl"]


def _get_db() -> sqlite3.Connection:
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS translations "
        "(hash TEXT PRIMARY KEY, translated TEXT)"
    )
    conn.commit()
    return conn


def _cache_key(text: str, target_lang: str, provider: str) -> str:
    return hashlib.sha256(f"{text}|{target_lang}|{provider}".encode()).hexdigest()


def _from_cache(key: str) -> Optional[str]:
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT translated FROM translations WHERE hash = ?", (key,)
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _to_cache(key: str, translated: str) -> None:
    try:
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO translations VALUES (?, ?)", (key, translated)
        )
        conn.commit()
    except Exception:
        pass


def translate_lines(
    lines: list[str],
    source_lang: str,
    target_lang: str,
    provider: str = "google",
) -> list[str]:
    """Translate list of lines. Returns same-length list. Falls back through providers."""
    if source_lang == target_lang:
        return lines

    joined = "\n".join(lines)
    cache_key = _cache_key(joined, target_lang, provider)
    cached = _from_cache(cache_key)
    if cached:
        result = cached.split("\n")
        if len(result) == len(lines):
            return result

    translated = _try_translate(joined, source_lang, target_lang, provider)
    if translated is None:
        return lines  # all providers failed

    _to_cache(cache_key, translated)
    result = translated.split("\n")
    # Guard against line count mismatch
    if len(result) != len(lines):
        return lines
    return result


def _try_translate(
    text: str, src: str, tgt: str, preferred_provider: str
) -> Optional[str]:
    ordered = [preferred_provider] + [p for p in PROVIDERS if p != preferred_provider]
    for provider in ordered:
        result = _translate_with(text, src, tgt, provider)
        if result is not None:
            return result
    return None


def _translate_with(text: str, src: str, tgt: str, provider: str) -> Optional[str]:
    try:
        if provider == "google":
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source=src, target=tgt).translate(text)

        if provider == "libre":
            from deep_translator import LibreTranslator
            url = os.environ.get("LIBRE_TRANSLATE_URL", "https://libretranslate.com")
            api_key = os.environ.get("LIBRE_TRANSLATE_KEY", "")
            return LibreTranslator(
                source=src, target=tgt, url=url, api_key=api_key
            ).translate(text)

        if provider == "deepl":
            from deep_translator import DeepL
            api_key = os.environ.get("DEEPL_API_KEY", "")
            if not api_key:
                return None
            return DeepL(api_key=api_key, source=src, target=tgt).translate(text)

    except Exception:
        pass
    return None
