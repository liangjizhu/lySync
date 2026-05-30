import re
from dataclasses import dataclass, field


@dataclass
class LRCLine:
    time_ms: int
    text: str
    translated_text: str = field(default="", compare=False)


_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}):(\d{2})\.(\d{2,3})\]")
_WORD_TAG_RE = re.compile(r"<\d{1,2}:\d{2}\.\d{2,3}>")
_META_TAG_RE = re.compile(r"^\[(?:ar|ti|al|by|offset|length):[^\]]*\]$", re.IGNORECASE)


def parse_lrc(lrc_text: str) -> list[LRCLine]:
    """Parse LRC text into sorted list of LRCLine. Handles A2 word-level tags."""
    lines: list[LRCLine] = []

    for raw_line in lrc_text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        if _META_TAG_RE.match(raw_line):
            continue

        timestamps = _TIMESTAMP_RE.findall(raw_line)
        if not timestamps:
            continue

        # Strip all timestamp tags and word-level tags to get clean text
        text = _TIMESTAMP_RE.sub("", raw_line)
        text = _WORD_TAG_RE.sub("", text).strip()

        for min_s, sec_s, cs_s in timestamps:
            # Normalize centiseconds/milliseconds: pad to 3 digits
            cs_str = cs_s.ljust(3, "0")
            time_ms = (int(min_s) * 60 + int(sec_s)) * 1000 + int(cs_str)
            lines.append(LRCLine(time_ms=time_ms, text=text))

    lines.sort(key=lambda l: l.time_ms)
    return lines
