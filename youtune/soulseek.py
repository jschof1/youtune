"""Soulseek integration — search for higher-quality versions of a track.

Two backends:
  - sockseek (preferred): battle-tested external binary with smart matching, length
    verification, format filtering, retry logic. Auto-detected on PATH.
  - native (fallback): basic aioslsk-based search + download used when sockseek
    is unavailable.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .parser import ParsedTitle

log = logging.getLogger(__name__)

# ─── sockseek backend detection ────────────────────────────────────────────────

_SOCKSEEK_PATH: Optional[str] = None
_SOCKSEEK_CHECKED = False


def _find_sockseek() -> Optional[str]:
    """Locate the sockseek binary. Cached after first lookup."""
    global _SOCKSEEK_PATH, _SOCKSEEK_CHECKED
    if _SOCKSEEK_CHECKED:
        return _SOCKSEEK_PATH
    _SOCKSEEK_CHECKED = True
    _SOCKSEEK_PATH = shutil.which("sockseek")
    if _SOCKSEEK_PATH:
        log.debug("sockseek found at %s", _SOCKSEEK_PATH)
    return _SOCKSEEK_PATH


def has_sockseek() -> bool:
    """Return True if the sockseek binary is available."""
    return _find_sockseek() is not None


def _write_sockseek_config(username: str, password: str, output_dir: Path) -> Path:
    """Write a temporary sockseek config file. Returns path."""
    config = tempfile.NamedTemporaryFile(
        mode="w", suffix=".conf", prefix="youtune-sockseek-", delete=False,
    )
    config.write(f"username = {username}\n")
    config.write(f"password = {password}\n")
    config.write("pref-format = flac,mp3\n")
    config.write("format = flac,mp3\n")
    config.write("no-write-index = true\n")
    config.write(f"path = {output_dir}\n")
    config.close()
    return Path(config.name)


def _run_sockseek_download(
    artist: str,
    title: str,
    output_dir: Path,
    username: str,
    password: str,
    prefer_flac: bool = True,
    length_seconds: Optional[int] = None,
) -> Optional[Path]:
    """Download a single track via sockseek subprocess. Returns path or None."""
    sockseek = _find_sockseek()
    if not sockseek:
        return None

    config_path = _write_sockseek_config(username, password, output_dir)

    # Build query. Sockseek uses "Artist - Title" format for song mode.
    query = f"{artist} - {title}" if artist else title
    pref_format = "flac" if prefer_flac else "mp3"

    # Build command
    cmd = [
        sockseek,
        query,
        "--song",
        "--config", str(config_path),
        "--pref-format", pref_format,
        "--no-progress",
        "--no-skip-existing",
    ]

    if length_seconds:
        # Pass track length for strict matching (sockseek matches within 3s by default)
        cmd.extend(["--cond", f"length-tol=5"])

    log.info("sockseek: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max
        )
        log.debug("sockseek stdout:\n%s", result.stdout)
        if result.returncode != 0:
            log.warning("sockseek exited with code %d: %s", result.returncode, result.stderr[-500:])
    except subprocess.TimeoutExpired:
        log.warning("sockseek timed out")
    except FileNotFoundError:
        log.error("sockseek binary not found at %s", sockseek)
    finally:
        # Clean up temp config
        config_path.unlink(missing_ok=True)

    # Find the downloaded file. sockseek places files in output_dir (possibly nested).
    # Look for audio files modified in the last few minutes.
    cutoff = os.stat(output_dir).st_mtime if output_dir.exists() else 0
    candidates = []
    for ext in (".flac", ".mp3", ".m4a", ".ogg"):
        for f in output_dir.rglob(f"*{ext}"):
            try:
                if f.stat().st_mtime >= cutoff:
                    candidates.append((f.stat().st_mtime, f))
            except OSError:
                pass
    if candidates:
        candidates.sort(reverse=True)
        best = candidates[0][1]
        log.info("sockseek downloaded: %s", best.name)
        return best
    return None


# ─── native aioslsk backend ────────────────────────────────────────────────────

BITRATE_ATTR_KEY = 0


def _check_aioslsk() -> bool:
    try:
        import aioslsk  # noqa: F401
        return True
    except ImportError:
        return False


def _get_bitrate(file_data) -> int:
    try:
        for attr in file_data.attributes:
            if attr.key == BITRATE_ATTR_KEY:
                return int(attr.value) if attr.value else 0
    except Exception:
        pass
    return 0


def _clean_query(text: str) -> str:
    text = text.replace("'", "")
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _build_queries(artist: str, title: str) -> list[str]:
    clean_artist = _clean_query(artist)
    clean_title = _clean_query(title)
    queries = []
    if clean_artist:
        queries.append(f"{clean_artist} {clean_title}")
    queries.append(clean_title)
    if clean_artist:
        queries.append(f"{clean_artist} - {clean_title}")
    return queries


async def _test_login_native(username: str, password: str) -> tuple[bool, str]:
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
        if any(w in error_msg for w in ("invalid", "bad", "password", "auth")):
            return False, "Invalid username or password"
        if "ban" in error_msg:
            return False, "Account is banned"
        if any(w in error_msg for w in ("connect", "timeout", "refused")):
            return False, "Cannot reach Soulseek server — check your internet connection"
        return False, f"Connection failed: {e}"


async def _do_search_native(client, query: str, wait_seconds: int = 15) -> list:
    log.info("Soulseek query: %s", query)
    search_request = await client.searches.search(query)
    for i in range(wait_seconds):
        await asyncio.sleep(1)
        n_results = len(search_request.results)
        n_files = sum(len(r.shared_items) for r in search_request.results)
        if n_files > 0:
            log.info("Soulseek: %d results, %d files after %ds", n_results, n_files, i + 1)
            await asyncio.sleep(5)
            break
        if (i + 1) % 5 == 0:
            log.info("Soulseek: 0 results after %ds...", i + 1)
    return search_request.results


async def _search_and_download_native(
    artist: str,
    title: str,
    output_dir: Path,
    username: str,
    password: str,
    prefer_flac: bool = True,
    min_bitrate: int = 256,
) -> Optional[Path]:
    if not _check_aioslsk():
        log.error("aioslsk not installed. Run: pip install 'youtune[soulseek]'")
        return None

    # Suppress noisy aioslsk/UPnP logging
    for noisy in ("aioslsk", "async_upnp_client", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    try:
        from aioslsk.client import SoulSeekClient, Settings
        from aioslsk.settings import CredentialsSettings
        settings = Settings(
            credentials=CredentialsSettings(username=username, password=password),
        )
        client = SoulSeekClient(settings=settings)
        await client.start()
        log.info("Logged into Soulseek as %s", username)
        queries = _build_queries(artist, title)
        all_results = []
        for query in queries:
            results = await _do_search_native(client, query, wait_seconds=12)
            if results:
                all_results.extend(results)
                log.info("Found %d results with query: %s", len(results), query)
                break
            log.info("No results for: %s", query)
        if not all_results:
            log.info("No Soulseek results found for any query variation")
            await client.stop()
            return None
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
        download_name = Path(best_file.filename).name
        if hasattr(transfer, 'local_path') and transfer.local_path:
            actual = Path(transfer.local_path)
            if actual.exists():
                return actual
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


# ─── public API ────────────────────────────────────────────────────────────────

def test_soulseek_login(username: str, password: str) -> tuple[bool, str]:
    """Test Soulseek login credentials. Uses sockseek if available, else native."""
    if has_sockseek():
        # Quick check: run sockseek with --print results (dry run, no download)
        sockseek = _find_sockseek()
        config_path = _write_sockseek_config(username, password, Path.home() / "Downloads")
        try:
            result = subprocess.run(
                [sockseek, "test", "--song", "--config", str(config_path),
                 "--no-progress", "--print", "tracks"],
                capture_output=True, text=True, timeout=30,
            )
            config_path.unlink(missing_ok=True)
            # sockseek exits 0 on success, non-zero on auth failure
            if result.returncode == 0:
                return True, f"Connected as {username} (via sockseek)"
            combined = (result.stderr + result.stdout).lower()
            if "invalid" in combined or "bad" in combined or "password" in combined:
                return False, "Invalid username or password"
            if "ban" in combined:
                return False, "Account is banned"
            return False, f"Connection failed: {result.stderr[:200]}"
        except Exception as e:
            config_path.unlink(missing_ok=True)
            return False, f"Error: {e}"

    # Native fallback
    try:
        return asyncio.run(_test_login_native(username, password))
    except Exception as e:
        return False, f"Error: {e}"


def soulseek_upgrade(
    parsed: ParsedTitle,
    output_dir: Path,
    username: str,
    password: str,
    prefer_flac: bool = True,
    min_bitrate: int = 256,
) -> Optional[Path]:
    """
    Search Soulseek for a higher-quality version of the track.

    Uses sockseek backend if available (smart matching, length verification,
    format filtering, retries). Falls back to native aioslsk implementation.
    """
    # ── sockseek backend (preferred) ──
    if has_sockseek():
        log.info("Using sockseek backend for Soulseek upgrade")
        result = _run_sockseek_download(
            artist=parsed.artist,
            title=parsed.title,
            output_dir=output_dir,
            username=username,
            password=password,
            prefer_flac=prefer_flac,
        )
        if result:
            return result
        log.info("sockseek found nothing, trying native backend...")

    # ── native aioslsk backend (fallback) ──
    log.info("Using native aioslsk backend for Soulseek upgrade")
    try:
        return asyncio.run(
            _search_and_download_native(
                parsed.artist, parsed.title, output_dir,
                username, password, prefer_flac, min_bitrate,
            )
        )
    except Exception as e:
        log.warning("Soulseek upgrade failed: %s", e)
        return None
