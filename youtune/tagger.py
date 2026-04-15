"""MusicBrainz metadata lookup + Cover Art Archive + lrclib lyrics."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import musicbrainzngs
import requests

from .parser import ParsedTitle

log = logging.getLogger(__name__)

_initialized = False


def _init_mb():
    global _initialized
    if not _initialized:
        musicbrainzngs.set_useragent("youtune", "1.0.0", "https://github.com/jschof1/youtune")
        _initialized = True


@dataclass
class TrackMetadata:
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    year: str = ""
    track_number: str = ""
    genre: str = ""
    musicbrainz_recording_id: str = ""
    musicbrainz_artist_id: str = ""
    musicbrainz_release_id: str = ""
    cover_art_url: str = ""
    lyrics: str = ""
    sources: list[str] = field(default_factory=list)


def search_recording(parsed: ParsedTitle) -> Optional[TrackMetadata]:
    """
    Search MusicBrainz for a recording matching the parsed YouTube title.
    Returns the best TrackMetadata match or None.
    """
    _init_mb()
    meta = TrackMetadata()

    query_parts = []
    if parsed.artist:
        query_parts.append(f'artist:"{parsed.artist}"')
    if parsed.title:
        query_parts.append(f'recording:"{parsed.title}"')

    if not query_parts:
        return None

    query = " AND ".join(query_parts)

    try:
        result = musicbrainzngs.search_recordings(query=query, limit=5)
    except musicbrainzngs.WebServiceError as e:
        log.warning("MusicBrainz lookup failed: %s", e)
        return None

    recordings = result.get("recording-list", [])
    if not recordings:
        # Retry with looser search (title only)
        try:
            result = musicbrainzngs.search_recordings(
                query=f'recording:"{parsed.title}"', limit=5
            )
            recordings = result.get("recording-list", [])
        except musicbrainzngs.WebServiceError:
            return None

    if not recordings:
        return None

    rec = recordings[0]
    meta.title = rec.get("title", parsed.title)
    meta.musicbrainz_recording_id = rec.get("id", "")

    # Artist
    artist_credit = rec.get("artist-credit", [])
    if artist_credit:
        meta.artist = artist_credit[0].get("name", parsed.artist)
        meta.musicbrainz_artist_id = (
            artist_credit[0].get("artist", {}).get("id", "")
        )

    # Release / album info
    releases = rec.get("release-list", [])
    if releases:
        rel = releases[0]
        meta.album = rel.get("title", "")
        meta.musicbrainz_release_id = rel.get("id", "")
        date = rel.get("date", "")
        if date:
            meta.year = date[:4]
        for medium in rel.get("medium-list", []):
            for track in medium.get("track-list", []):
                if track.get("recording", {}).get("id") == meta.musicbrainz_recording_id:
                    meta.track_number = track.get("position", "")
                    break

    meta.sources.append("musicbrainz")
    return meta


def fetch_cover_art(release_id: str) -> Optional[bytes]:
    """Fetch front cover art from the Cover Art Archive. Returns image bytes or None."""
    if not release_id:
        return None

    url = f"https://coverartarchive.org/release/{release_id}/front-500"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            log.info("Cover art found for release %s", release_id)
            return resp.content
        log.debug("No cover art for release %s (HTTP %d)", release_id, resp.status_code)
    except requests.RequestException as e:
        log.warning("Cover art fetch failed: %s", e)
    return None


def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    """Fetch lyrics from lrclib (free, no API key)."""
    url = "https://lrclib.net/api/search"
    try:
        resp = requests.get(url, params={"q": f"{artist} {title}"}, timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            if results and isinstance(results, list):
                for r in results:
                    lyric = r.get("syncedLyrics") or r.get("plainLyrics")
                    if lyric:
                        return lyric.strip()
    except Exception as e:
        log.debug("Lyrics fetch failed: %s", e)
    return None
