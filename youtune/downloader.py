"""yt-dlp wrapper for downloading audio from YouTube (and thousands of other sites)."""

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _require(cmd: str) -> str:
    path = shutil.which(cmd)
    if not path:
        install = {
            "yt-dlp": "brew install yt-dlp  or  pip install yt-dlp",
            "ffmpeg": "brew install ffmpeg  or  apt install ffmpeg",
        }
        raise FileNotFoundError(f"{cmd} not found. Install: {install.get(cmd, '')}")
    return path


def download(
    url: str,
    output_dir: Path,
    quality: int = 0,
    normalize: bool = False,
) -> tuple[Path, str]:
    """
    Download audio from a URL as MP3.

    Returns:
        (filepath, video_title)
    """
    _require("yt-dlp")
    _require("ffmpeg")
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp", url,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", str(quality),
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        "--print", "after_move:filepath",
        "-o", str(output_dir / "%(title)s.%(ext)s"),
    ]
    if normalize:
        cmd.extend(["--postprocessor-args", "-af loudnorm=I=-14:TP=-1.5:LRA=11"])

    log.info("Downloading: %s", url)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    filepath = Path(result.stdout.strip())
    if not filepath.exists():
        mp3s = sorted(output_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if mp3s:
            filepath = mp3s[0]
        else:
            raise FileNotFoundError("Downloaded MP3 not found")

    log.info("Downloaded: %s", filepath.name)
    return filepath, filepath.stem


def download_playlist(
    url: str,
    output_dir: Path,
    quality: int = 0,
    normalize: bool = False,
) -> list[tuple[Path, str]]:
    """
    Download all videos in a playlist as MP3s.
    Returns list of (filepath, video_title).
    """
    _require("yt-dlp")
    _require("ffmpeg")
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp", url,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", str(quality),
        "--yes-playlist",
        "--no-warnings",
        "--quiet",
        "--print", "after_move:filepath",
        "-o", str(output_dir / "%(title)s.%(ext)s"),
    ]
    if normalize:
        cmd.extend(["--postprocessor-args", "-af loudnorm=I=-14:TP=-1.5:LRA=11"])

    log.info("Downloading playlist: %s", url)
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    tracks = []
    for line in result.stdout.strip().splitlines():
        fp = Path(line.strip())
        if fp.exists():
            tracks.append((fp, fp.stem))

    log.info("Downloaded %d tracks", len(tracks))
    return tracks
