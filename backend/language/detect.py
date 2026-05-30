from typing import Optional

CONFIDENCE_THRESHOLD = 0.85


def detect(lines: list[str]) -> Optional[str]:
    """Detect language from first 10 lyrics lines. Returns BCP-47 code or None."""
    sample = "\n".join(lines[:10])
    if not sample.strip():
        return None

    try:
        from langdetect import detect_langs
        results = detect_langs(sample)
        if results and results[0].prob >= CONFIDENCE_THRESHOLD:
            return results[0].lang
        # Low confidence — try lingua for better CJK / similar-language accuracy
        lang = _lingua_detect(sample)
        if lang:
            return lang
        # Fall back to langdetect top result
        return results[0].lang if results else None
    except Exception:
        return _lingua_detect(sample)


def _lingua_detect(text: str) -> Optional[str]:
    try:
        from lingua import LanguageDetectorBuilder
        detector = LanguageDetectorBuilder.from_all_languages().build()
        result = detector.detect_language_of(text)
        if result:
            # lingua uses ISO 639-1 codes via .iso_code_639_1
            code = result.iso_code_639_1
            return code.name.lower() if code else None
    except Exception:
        pass
    return None
