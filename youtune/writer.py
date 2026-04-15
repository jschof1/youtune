"""Write ID3 tags, cover art, and lyrics to MP3 files."""

import logging
from pathlib import Path
from typing import Optional

from mutagen.id3 import (
    APIC, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TRCK, USLT,
)
from mutagen.mp3 import MP3

from .tagger import TrackMetadata

log = logging.getLogger(__name__)


def apply_metadata(filepath: Path, meta: TrackMetadata) -> bool:
    """Write all available metadata into the MP3 file. Returns True if any tags were written."""
    try:
        audio = MP3(str(filepath))
    except Exception:
        log.error("Cannot open MP3 for tagging: %s", filepath)
        return False

    try:
        tags = audio.tags
        if tags is None:
            tags = ID3()
            audio.tags = tags
    except ID3NoHeaderError:
        tags = ID3()
        audio.add(tags)

    written = False

    if meta.title:
        tags.add(TIT2(encoding=3, text=[meta.title])); written = True
    if meta.artist:
        tags.add(TPE1(encoding=3, text=[meta.artist])); written = True
    if meta.album_artist:
        tags.add(TPE2(encoding=3, text=[meta.album_artist])); written = True
    elif meta.artist:
        tags.add(TPE2(encoding=3, text=[meta.artist])); written = True
    if meta.album:
        tags.add(TALB(encoding=3, text=[meta.album])); written = True
    if meta.year:
        tags.add(TDRC(encoding=3, text=[meta.year])); written = True
    if meta.track_number:
        tags.add(TRCK(encoding=3, text=[meta.track_number])); written = True
    if meta.genre:
        tags.add(TCON(encoding=3, text=[meta.genre])); written = True
    if meta.lyrics:
        tags.add(USLT(encoding=3, lang="eng", desc="Lyrics", text=meta.lyrics)); written = True

    audio.save()
    if written:
        log.info("Tags written to %s", filepath.name)
    return written


def embed_cover_art(filepath: Path, image_data: bytes) -> bool:
    """Embed cover art (JPEG/PNG) into an MP3 file."""
    try:
        audio = MP3(str(filepath))
        tags = audio.tags
        if tags is None:
            tags = ID3()
            audio.tags = tags

        tags.delall("APIC")
        mime = "image/png" if image_data[:4] == b"\x89PNG" else "image/jpeg"

        tags.add(APIC(
            encoding=3, mime=mime, type=3, desc="Cover", data=image_data,
        ))
        audio.save()
        log.info("Cover art embedded in %s", filepath.name)
        return True
    except Exception as e:
        log.error("Failed to embed cover art: %s", e)
        return False
