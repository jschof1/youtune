"""Soulseek integration — search for higher-quality versions of a track."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .parser import ParsedTitle

log = logging.getLogger(__name__)


def _check_aioslsk() -> bool:
    try:
        import aioslsk  # noqa: F401
        return True
    except ImportError:
        return False


async def _test_login(username: str, password: str) -> tuple[bool, str]:
    """Test Soulseek login credentials. Returns (success, message)."""
    if not _check_aioslsk():
        return False, "aioslsk not installed. Run: pip install 'youtune[soulseek]'"

    try:
        from aioslsk.client import SoulSeekClient, Settings
        from aioslsk.settings import CredentialsSettings, NetworkSettings

        settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
        )
        client = SoulSeekClient(settings=settings)
        await client.start()  # connects + logs in
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


def _get_bitrate(file_data) -> int:
    """Extract bitrate from a FileData's attributes."""
    try:
        for attr in file_data.attributes:
            # Attribute has .name and .value — bitrate attribute
            if hasattr(attr, 'name') and 'bitrate' in str(attr.name).lower():
                return int(attr.value) if attr.value else 0
            # Some versions just use numeric attribute type
            if hasattr(attr, 'type') and attr.type == 0:  # bitrate
                return int(attr.value) if attr.value else 0
    except Exception:
        pass
    return 0


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

    query = f"{artist} {title}"
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

        # Give search a few seconds to collect results
        await asyncio.sleep(5)

        results = search_request.results
        if not results:
            log.info("No Soulseek results for: %s", query)
            await client.stop()
            return None

        candidates = []
        for result in results:
            for item in result.shared_items:
                fn = item.filename.lower()
                ext = item.extension.lower() if item.extension else ""
                if ext not in [".mp3", ".flac"]:
                    continue
                bitrate = _get_bitrate(item)
                score = bitrate
                if ext == ".flac" and prefer_flac:
                    score += 500
                if score >= min_bitrate:
                    candidates.append((score, result.username, item))

        if not candidates:
            log.info("No high-quality Soulseek results for: %s", query)
            await client.stop()
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_user, best_file = candidates[0]

        log.info(
            "Soulseek upgrade: %s (%d) from %s",
            best_file.filename, best_score, best_user,
        )

        download_path = output_dir / Path(best_file.filename).name

        transfer = await client.transfers.download(
            username=best_user,
            filename=best_file.filename,
        )

        # Wait for download to complete (with timeout)
        for _ in range(300):  # max 5 minutes
            await asyncio.sleep(1)
            if transfer.is_complete():
                break

        await client.stop()

        # The transfer saves to Soulseek's download dir — check if it exists
        # aioslsk puts downloads in a configured directory
        if download_path.exists():
            return download_path

        # Try to find the file in the transfer
        if hasattr(transfer, 'local_path') and transfer.local_path:
            actual = Path(transfer.local_path)
            if actual.exists():
                return actual

        log.warning("Download completed but file not found at expected path")
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
