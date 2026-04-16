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


def _clean_query(text: str) -> str:
    """Strip punctuation that hurts Soulseek matching."""
    # Remove apostrophes (I'll -> Ill, Don't -> Dont)
    text = text.replace("'", "")
    # Remove other problematic punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _build_queries(artist: str, title: str) -> list[str]:
    """
    Build multiple search queries to maximize match probability.
    Soulseek users name files inconsistently, so try variations.
    """
    clean_artist = _clean_query(artist)
    clean_title = _clean_query(title)
    queries = []

    # Full query: artist + title
    if clean_artist:
        queries.append(f"{clean_artist} {clean_title}")

    # Just the title (some users file under compilations)
    queries.append(clean_title)

    # Artist - Title (common naming convention)
    if clean_artist:
        queries.append(f"{clean_artist} - {clean_title}")

    return queries


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


async def _do_search(client, query: str, wait_seconds: int = 15) -> list:
    """Execute a single search and wait for results."""
    log.info("Soulseek query: %s", query)
    search_request = await client.searches.search(query)

    for i in range(wait_seconds):
        await asyncio.sleep(1)
        n_results = len(search_request.results)
        n_files = sum(len(r.shared_items) for r in search_request.results)
        if n_files > 0:
            log.info("Soulseek: %d results, %d files after %ds", n_results, n_files, i + 1)
            # Give it a bit more time to accumulate once we start seeing results
            await asyncio.sleep(5)
            break
        if (i + 1) % 5 == 0:
            log.info("Soulseek: 0 results after %ds...", i + 1)

    return search_request.results


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

    try:
        from aioslsk.client import SoulSeekClient, Settings
        from aioslsk.settings import CredentialsSettings

        settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
        )
        client = SoulSeekClient(settings=settings)
        await client.start()
        log.info("Logged into Soulseek as %s", username)

        # Try multiple query variations until we find results
        queries = _build_queries(artist, title)
        all_results = []

        for query in queries:
            results = await _do_search(client, query, wait_seconds=12)
            if results:
                all_results.extend(results)
                log.info("Found %d results with query: %s", len(results), query)
                break  # stop searching once we get hits
            log.info("No results for: %s", query)

        if not all_results:
            log.info("No Soulseek results found for any query variation")
            await client.stop()
            return None

        # Collect and rank all audio files
        candidates = []
        for result in all_results:
            for item in result.shared_items:
                ext = (item.extension or "").lower()
                if ext not in [".mp3", ".flac"]:
                    continue
                bitrate = _get_bitrate(item)
                score = bitrate
                if ext == ".flac" and prefer_flac:
                    score += 500
                if result.has_free_slots:
                    score += 50
                score += min(result.avg_speed // 100, 50)
                if score >= min_bitrate:
                    candidates.append((score, result.username, item, bitrate))

        if not candidates:
            # Lower the bar: try any audio file regardless of bitrate
            for result in all_results:
                for item in result.shared_items:
                    ext = (item.extension or "").lower()
                    if ext not in [".mp3", ".flac", ".m4a", ".ogg", ".wav"]:
                        continue
                    bitrate = _get_bitrate(item)
                    score = bitrate or 128
                    if ext == ".flac":
                        score += 500
                    candidates.append((score, result.username, item, bitrate))

            if not candidates:
                log.info("No audio files found in Soulseek results")
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

        # Wait for download to complete (max 5 minutes)
        for _ in range(300):
            await asyncio.sleep(1)
            if hasattr(transfer, 'is_complete') and callable(transfer.is_complete):
                if transfer.is_complete():
                    break
            elif hasattr(transfer, 'state'):
                try:
                    from aioslsk.transfer.model import TransferState
                    if transfer.state in (TransferState.COMPLETE, TransferState.UPLOADED, TransferState.DOWNLOADED):
                        break
                except ImportError:
                    pass

        await client.stop()

        # Locate the downloaded file
        download_name = Path(best_file.filename).name

        if hasattr(transfer, 'local_path') and transfer.local_path:
            actual = Path(transfer.local_path)
            if actual.exists():
                return actual

        # Search common download locations
        search_dirs = [
            Path.home() / "Soulseek Downloads",
            Path.home() / "Downloads" / "Soulseek",
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
