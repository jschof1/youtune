"""Parse YouTube video titles into artist + song name."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedTitle:
    artist: str
    title: str
    confidence: float  # 0.0–1.0


# Patterns ordered by specificity. First match wins.
PATTERNS = [
    # "Artist - Song (Official Music Video)" etc.
    re.compile(
        r"^(?P<artist>.+?)\s*[-–—]\s*(?P<title>.+?)(?:\s*[\(\[](?:official|music|lyric|audio|video|visualiser|visualizer|hd|4k|remaster).+)?$",
        re.IGNORECASE,
    ),
    # "Artist «Song»" or "Artist 『Song』"
    re.compile(r"^(?P<artist>.+?)\s*[«『【]\s*(?P<title>.+?)[»』】]"),
    # '"Song" by Artist'
    re.compile(r'^["\'](?P<title>.+?)["\']\s+by\s+(?P<artist>.+?)$', re.IGNORECASE),
    # "Artist | Song"
    re.compile(r"^(?P<artist>.+?)\s*[|]\s*(?P<title>.+?)$"),
    # "Artist „Song"
    re.compile(r"^(?P<artist>.+?)\s*[\u201E\u201C\u201D]\s*(?P<title>.+?)$"),
]

# Junk to strip from anywhere in the title
JUNK_PATTERNS = [
    re.compile(r"\(?\b(official\s+)?(music\s+)?video\b\)?", re.IGNORECASE),
    re.compile(r"\(?\b(official\s+)?(audio|lyric(s)?|visuali[sz]er)\b\)?", re.IGNORECASE),
    re.compile(r"\(?\b(hd|4k|hq|remaster(ed)?|restored)\b\)?", re.IGNORECASE),
    re.compile(r"\(?\bfull\s+song\b\)?", re.IGNORECASE),
    re.compile(r"\(?\bfeat\.?\s+[^)]+\)?", re.IGNORECASE),
    re.compile(r"\[\s*[^]]*?\s*\]", re.IGNORECASE),
    re.compile(r"【\s*[^】]*?\s*】"),
]


def clean_title(text: str) -> str:
    """Remove common YouTube junk from a title string."""
    for pat in JUNK_PATTERNS:
        text = pat.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def parse_title(raw: str) -> ParsedTitle:
    """
    Parse a YouTube video title into artist + song.

    Returns a ParsedTitle with a confidence score:
        0.9 = strong pattern match (dash, pipe, quotes)
        0.7 = fallback separator split
        0.3 = no artist found, whole title used as song
    """
    raw = raw.strip()

    for pat in PATTERNS:
        m = pat.match(raw)
        if m:
            artist = clean_title(m.group("artist")).strip()
            title = clean_title(m.group("title")).strip()
            if artist and title:
                return ParsedTitle(artist=artist, title=title, confidence=0.9)

    # Fallback: split on first dash
    for sep in [" - ", " – ", " — "]:
        if sep in raw:
            parts = raw.split(sep, 1)
            artist = clean_title(parts[0]).strip()
            title = clean_title(parts[1]).strip()
            if artist and title:
                return ParsedTitle(artist=artist, title=title, confidence=0.7)

    # Last resort: use cleaned title as song name
    cleaned = clean_title(raw)
    return ParsedTitle(artist="", title=cleaned, confidence=0.3)
