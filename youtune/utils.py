"""Utility helpers."""

import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > 200:
        name = name[:200].rsplit(" ", 1)[0]
    return name


def format_filename(artist: str, title: str, ext: str = "mp3") -> str:
    """Format a clean filename: 'Artist - Title.mp3'"""
    name = f"{artist} - {title}" if artist else title
    return f"{sanitize_filename(name)}.{ext}"
