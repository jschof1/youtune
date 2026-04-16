"""Soulseek integration — search for higher-quality versions of a track."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from .parser import ParsedTitle

log = logging.getLogger(__name__)

# Attribute key 0 = BITRATE in Soulseek protocol
BITRATE_ATTR_KEY = 0


def _check_aioslsk() -> bool:
    try:
        import aioslsk  # noqa: F401
        return True
    except ImportError:
        return False


def _get_bitrate(file_data) -> int:
    """Extract bitrate from a FileData's attributes."""
    try:
        for attr in file_data.attributes:
            if attr.key == BITRATE_ATTR_KEY:
                return int(attr.value) if attr.value else 0
    except Exception:
        pass
    return 0


def _clean_query(artist: str, title: str) -> str:
    """
    Clean a search query for Soulseek.
    Strip punctuation that hurts matching (apostrophes, special chars).
    """
    q = f"{artist} {title}"
    # Remove apostrophes (I'll -> Ill, Don't -> Dont)
    q = q.replace("'", "")
    # Remove other punctuation that hurts search
    q = re.sub(r'[^\w\s]', ' ', q)
    # Collapse whitespace
    q = re.sub(r'\s+', ' ', q).strip()
    return q


async def _test_login(username: str, password: str) -> tuple[bool, str]:
    """Test Soulseek login credentials. Returns (success, message)."""
    if not _check_aioslsk():
        return False, "aioslsk not installed. Run: pip install 'youtune[soulseek]'"

    try:
        from aioslsk.client import SoulSeekClient, Settings
        from aioslsk.settings import CredentialsSettings

        settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
        )
        client = SoulSeekClient(settings=settings)
        await client.start()
        await client.stop()
        return True, f"Connected as {username}"
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid" in error_msg or "bad" in error_msg or "password" in error_msg or "auth" in error_msg:
            return False, "Invalid username or password"
        if "ban" in error_msg:
            return False, "Account is banned"
        if "connect" in error_msg or "timeout" in error_msg or "refused" in error_msg:
            return False, "Cannot reach Soulseek server — check your internet connection"
        return False, f"Connection failed: {e}"


def test_soulseek_login(username: str, password: str) -> tuple[bool, str]:
    """Sync wrapper: test Soulseek login."""
    try:
        return asyncio.run(_test_login(username, password))
    except Exception as e:
        return False, f"Error: {e}"


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
    if not _check_aioslsk():
        log.error("aioslsk not installed. Run: pip install 'youtune[soulseek]'")
        return None

    query = _clean_query(artist, title)
    log.info("Soulseek query: %s", query)

    try:
        from aioslsk.client import SoulSeekClient, Settings
        from aioslsk.settings import CredentialsSettings

        settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
        )
        client = SoulSeekClient(settings=settings)
        await client.start()
        log.info("Logged into Soulseek as %s", username)

        search_request = await client.searches.search(query)

        # Wait for results to accumulate from the P2P network.
        # Soulseek is distributed — results trickle in over time.
        # Check periodically and stop early if we have enough.
        max_wait = 20  # seconds total
        check_interval = 2
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            num_results = len(search_request.results)
            total_files = sum(len(r.shared_items) for r in search_request.results)
            log.info("Soulseek: %d results, %d files after %ds", num_results, total_files, elapsed)

            # Stop waiting once we have a decent amount of results
            if total_files >= 5 or elapsed >= 10:
                break

        results = search_request.results
        if not results:
            log.info("No Soulseek results for: %s", query)
            await client.stop()
            return None

        # Collect and rank all audio files
        candidates = []
        for result in results:
            for item in result.shared_items:
                fn = (item.filename or "").lower()
                ext = (item.extension or "").lower()
                if ext not in [".mp3", ".flac"]:
                    continue
                bitrate = _get_bitrate(item)
                score = bitrate
                if ext == ".flac" and prefer_flac:
                    score += 500
                # Prefer users with free slots and fast speed
                if result.has_free_slots:
                    score += 50
                score += min(result.avg_speed // 100, 50)  # small bonus for speed
                if score >= min_bitrate:
                    candidates.append((score, result.username, item, bitrate))

        if not candidates:
            log.info("No high-quality Soulseek results for: %s (found %d files but none >= %dkbps)",
                      query, sum(len(r.shared_items) for r in results), min_bitrate)
            await client.stop()
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_user, best_file, best_bitrate = candidates[0]

        log.info(
            "Soulseek best: %s (%dkbps, score %d) from %s",
            Path(best_file.filename).name, best_bitrate, best_score, best_user,
        )

        transfer = await client.transfers.download(
            username=best_user,
            filename=best_file.filename,
        )

        # Wait for download to complete (with timeout)
        for _ in range(300):  # max 5 minutes
            await asyncio.sleep(1)
            # Check transfer state
            if hasattr(transfer, 'is_complete') and callable(transfer.is_complete):
                if transfer.is_complete():
                    break
            elif hasattr(transfer, 'state'):
                from aioslsk.transfer.model import TransferState
                if transfer.state in (TransferState.COMPLETE, TransferState.UPLOADED, TransferState.DOWNLOADED):
                    break

        await client.stop()

        # Find where the file was saved
        # aioslsk saves to a downloads directory — try to locate it
        download_name = Path(best_file.filename).name

        # Check if transfer has a local_path attribute
        if hasattr(transfer, 'local_path') and transfer.local_path:
            actual = Path(transfer.local_path)
            if actual.exists():
                return actual

        # Search common download locations
        import os
        search_dirs = [
            Path.home() / "Soulseek Downloads",
            Path.home() / "Downloads",
            Path.home() / ".aioslsk" / "downloads",
        ]
        for d in search_dirs:
            if d.exists():
                for f in d.rglob(download_name):
                    if f.exists():
                        return f

        log.warning("Download completed but could not locate file: %s", download_name)
        return None

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
            _search_and_download(
                parsed.artist, parsed.title, output_dir,
                username, password, prefer_flac, min_bitrate,
            )
        )
    except Exception as e:
        log.warning("Soulseek upgrade failed: %s", e)
        return None
