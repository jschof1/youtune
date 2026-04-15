"""Soulseek integration — search for higher-quality versions of a track."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .parser import ParsedTitle

log = logging.getLogger(__name__)


async def _search_and_download(
    artist: str,
    title: str,
    output_dir: Path,
    username: str,
    password: str,
    prefer_flac: bool = True,
    min_bitrate: int = 256,
) -> Optional[Path]:
    """Search Soulseek and download the best version. Returns path or None."""
    try:
        import aioslsk
        from aioslsk.client import SoulseekClient
    except ImportError:
        log.error(
            "Soulseek support requires the 'soulseek' extra.\n"
            "Install with: pip install youtune[soulseek]"
        )
        return None

    query = f"{artist} {title}"
    try:
        client = SoulseekClient()
        await client.start()
        await client.login(username, password)
        log.info("Logged into Soulseek as %s", username)

        results = await client.search(query)
        if not results:
            log.info("No Soulseek results for: %s", query)
            return None

        candidates = []
        for result in results:
            for file in result.files:
                fn = file.filename.lower()
                if not any(fn.endswith(ext) for ext in [".mp3", ".flac"]):
                    continue
                score = file.bitrate or 0
                if fn.endswith(".flac") and prefer_flac:
                    score += 500
                if score >= min_bitrate:
                    candidates.append((score, result, file))

        if not candidates:
            log.info("No high-quality Soulseek results for: %s", query)
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, best_result, best_file = candidates[0]

        log.info("Soulseek upgrade: %s (%d kbps) from %s", best_file.filename, _score, best_result.username)
        download_path = output_dir / Path(best_file.filename).name
        await client.download(best_result.username, best_file.filename, str(download_path))
        await client.stop()
        return download_path

    except Exception as e:
        log.warning("Soulseek download failed: %s", e)
        return None


def soulseek_upgrade(
    parsed: ParsedTitle,
    output_dir: Path,
    username: str,
    password: str,
    prefer_flac: bool = True,
    min_bitrate: int = 256,
) -> Optional[Path]:
    """Sync wrapper: search Soulseek for a better version."""
    try:
        return asyncio.run(
            _search_and_download(parsed.artist, parsed.title, output_dir, username, password, prefer_flac, min_bitrate)
        )
    except Exception as e:
        log.warning("Soulseek upgrade failed: %s", e)
        return None
