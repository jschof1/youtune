"""youtune CLI — the main entry point."""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .config import load_config, save_config, get_soulseek_creds, CONFIG_FILE
from .downloader import download, download_playlist
from .parser import parse_title
from .soulseek import soulseek_upgrade, test_soulseek_login
from .tagger import TrackMetadata, search_recording, fetch_cover_art, fetch_lyrics
from .utils import sanitize_filename, format_filename
from .writer import apply_metadata, embed_cover_art

console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )
    logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)


# ─── login ────────────────────────────────────────────────────────────────────

def cmd_login(args):
    """Interactive first-time setup: save Soulseek credentials."""
    console.print()
    console.print(Panel(
        "[bold]youtune login[/]\n[dim]Connect your Soulseek account for quality upgrades[/]",
        border_style="bright_blue",
        padding=(0, 2),
    ))
    console.print()
    console.print("  Soulseek is a P2P network where people share FLAC & 320kbps music.")
    console.print("  youtune can search it for higher-quality versions of your downloads.")
    console.print()
    console.print("  [dim]Don't have an account? Create one at https://www.soulseekqt.net/[/]")
    console.print()

    config = load_config()

    # Show current value as default
    current_user = config.get("soulseek_user", "")
    default_hint = f" [dim](current: {current_user})[/]" if current_user else ""

    username = Prompt.ask(
        f"  [cyan]Soulseek username[/]{default_hint}",
        default=current_user or None,
    )
    password = Prompt.ask(
        f"  [cyan]Soulseek password[/]",
        password=True,
    )

    if not username or not password:
        console.print("\n  [red]Username and password are required.[/]")
        sys.exit(1)

    config["soulseek_user"] = username
    config["soulseek_pass"] = password

    console.print()
    with console.status("[bold green]Testing connection..."):
        ok, msg = test_soulseek_login(username, password)

    if ok:
        save_config(config)
        console.print(f"  ✅ [bold green]Connected![/] Logged into Soulseek as [cyan]{username}[/]")
        console.print(f"  📁 Config saved to [dim]{CONFIG_FILE}[/]")
        console.print()
        console.print("  Now run:")
        console.print(f"    [bold]youtune[/] \"https://youtube.com/watch?v=...\" [cyan]--soulseek[/]")
        console.print()
        console.print("  [dim]Your credentials are saved. You won't need to pass --soulseek-user/pass again.[/]")
    else:
        console.print(f"  ❌ [red]Login failed:[/] {msg}")
        console.print()
        console.print("  [dim]Check your username and password at https://www.slsknet.org/[/]")
        console.print(f"  [dim]Run [bold]youtune login[/] to try again.[/]")
        sys.exit(1)

    console.print()


# ─── status ───────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show current config and connection status."""
    console.print()
    console.print(Panel(
        f"[bold]youtune[/] [dim]v{__version__}[/] — Status",
        border_style="bright_blue",
        padding=(0, 2),
    ))
    console.print()

    config = load_config()

    table = Table(show_header=True, header_style="bold cyan", grid=True)
    table.add_column("Setting")
    table.add_column("Value")

    # Config values
    slsk_user = config.get("soulseek_user", "")
    output_dir = config.get("output_dir", "~/Downloads")
    quality = config.get("quality", 0)
    normalize = config.get("normalize", False)
    lyrics = config.get("lyrics", False)

    table.add_row("Config file", str(CONFIG_FILE))
    table.add_row("Default output", output_dir)
    table.add_row("Default quality", str(quality))
    table.add_row("Normalize", "✅ on" if normalize else "off")
    table.add_row("Lyrics", "✅ on" if lyrics else "off")

    if slsk_user:
        table.add_row("Soulseek user", slsk_user)
    else:
        table.add_row("Soulseek", "[yellow]not configured — run [bold]youtune login[/][/]")

    console.print(table)

    # Test Soulseek connection if we have creds
    if slsk_user and config.get("soulseek_pass"):
        console.print()
        with console.status("[bold green]Testing Soulseek connection..."):
            ok, msg = test_soulseek_login(slsk_user, config["soulseek_pass"])

        if ok:
            console.print(f"  🔗 [green]Soulseek: Connected as {slsk_user}[/]")
        else:
            console.print(f"  🔗 [red]Soulseek: {msg}[/]")
            console.print(f"     [dim]Run [bold]youtune login[/] to update your credentials.[/]")

    console.print()


# ─── download ─────────────────────────────────────────────────────────────────

def _resolve_soulseek_creds(args) -> tuple:
    """Resolve Soulseek credentials: CLI flags > saved config."""
    config = load_config()

    user = getattr(args, "soulseek_user", None) or config.get("soulseek_user", "")
    pas = getattr(args, "soulseek_pass", None) or config.get("soulseek_pass", "")
    return user, pas


def _process_track(filepath: Path, video_title: str, args) -> bool:
    """Full pipeline: parse → tag → art → lyrics → rename → soulseek upgrade."""
    log = logging.getLogger(__name__)

    # 1. Parse the YouTube title
    parsed = parse_title(video_title)
    console.print()
    if parsed.artist:
        console.print(f"  🎵 [cyan]{parsed.artist}[/] — [white]{parsed.title}[/] [dim](confidence: {parsed.confidence:.0%})[/]")
    else:
        console.print(f"  🎵 [white]{parsed.title}[/] [dim](confidence: {parsed.confidence:.0%})[/]")

    # 2. Start metadata from parsed title
    meta = TrackMetadata()
    if parsed.confidence >= 0.7 and parsed.artist:
        meta.artist = parsed.artist
        meta.title = parsed.title

    # 3. MusicBrainz lookup
    if not args.no_tag:
        with console.status("[bold green]Searching MusicBrainz..."):
            mb_meta = search_recording(parsed)
        if mb_meta:
            meta = mb_meta
            console.print("  ✅ [green]Metadata found[/] via MusicBrainz")
            if meta.album:
                console.print(f"     📀 Album: [magenta]{meta.album}[/]")
            if meta.year:
                console.print(f"     📅 Year:  [yellow]{meta.year}[/]")
            if meta.track_number:
                console.print(f"     #️⃣  Track: [blue]{meta.track_number}[/]")
        else:
            console.print("  ⚠️  [yellow]No MusicBrainz match — using parsed title[/]")

    # 4. Lyrics
    if args.lyrics and meta.artist and meta.title:
        with console.status("[bold green]Fetching lyrics..."):
            lyrics = fetch_lyrics(meta.artist, meta.title)
        if lyrics:
            meta.lyrics = lyrics
            lines = lyrics.count("\n") + 1
            console.print(f"  📝 [green]Lyrics found[/] ({lines} lines)")
        else:
            console.print("  📝 [dim]No lyrics found[/]")

    # 5. Write ID3 tags
    if not args.no_tag:
        apply_metadata(filepath, meta)

    # 6. Cover art
    if not args.no_art and meta.musicbrainz_release_id:
        with console.status("[bold green]Fetching cover art..."):
            art = fetch_cover_art(meta.musicbrainz_release_id)
        if art:
            embed_cover_art(filepath, art)
            console.print("  🖼️  [green]Cover art embedded[/]")
        else:
            console.print("  🖼️  [dim]No cover art found[/]")

    # 7. Smart rename
    if not args.no_rename and meta.artist and meta.title:
        new_name = format_filename(meta.artist, meta.title)
        new_path = filepath.parent / new_name
        if new_path != filepath:
            if new_path.exists():
                stem = new_path.stem
                new_path = filepath.parent / f"{stem} (1).mp3"
            filepath.rename(new_path)
            filepath = new_path
            console.print(f"  📝 Renamed → [cyan]{new_name}[/]")

    # 8. Soulseek upgrade
    if args.soulseek:
        slsk_user, slsk_pass = _resolve_soulseek_creds(args)

        if not slsk_user or not slsk_pass:
            console.print()
            console.print("  ⚠️  [yellow]Soulseek not configured.[/]")
            console.print("     Run [bold]youtune login[/] to connect your Soulseek account.")
            console.print("     Or pass [cyan]--soulseek-user[/] and [cyan]--soulseek-pass[/] flags.")
        else:
            console.print()
            with console.status(f"[bold green]Searching Soulseek as {slsk_user}..."):
                upgraded = soulseek_upgrade(
                    parsed=parsed,
                    output_dir=filepath.parent,
                    username=slsk_user,
                    password=slsk_pass,
                    prefer_flac=args.prefer_flac,
                    min_bitrate=args.min_bitrate,
                )
            if upgraded:
                console.print(f"  🔥 [bold green]Upgraded via Soulseek:[/] {upgraded.name}")
                if not args.keep_youtube:
                    filepath.unlink(missing_ok=True)
                    console.print("  🗑️  Removed YouTube version")
            else:
                console.print("  💎 [dim]No better Soulseek version found — keeping YouTube download[/]")

    return True


def cmd_download(args):
    """Handle single URL or playlist download."""
    url = args.url
    output_dir = Path(args.output).expanduser().resolve()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        console.print(f"\n[bold red]Error:[/] Cannot write to {output_dir}\n[dim]Specify a writable directory with -o, e.g. youtune URL -o ~/Music[/]")
        sys.exit(1)

    console.print()
    console.print(Panel(
        f"[bold white]youtune[/] [dim]v{__version__}[/]\n"
        f"[dim]The smartest YouTube → MP3 downloader[/]",
        border_style="bright_blue",
        padding=(0, 2),
    ))

    is_playlist = "list=" in url

    if is_playlist:
        console.print(f"  📂 [bold]Playlist detected[/]")
        tracks = download_playlist(url, output_dir, quality=args.quality, normalize=args.normalize)
        console.print(f"\n  [bold]Processing {len(tracks)} tracks...[/]")
        for filepath, title in tracks:
            try:
                _process_track(filepath, title, args)
            except Exception as e:
                console.print(f"  ❌ [red]Error: {e}[/]")
    else:
        filepath, title = download(url, output_dir, quality=args.quality, normalize=args.normalize)
        _process_track(filepath, title, args)

    console.print()
    console.print("[bold green]✨ Done![/]")


# ─── search ───────────────────────────────────────────────────────────────────

def cmd_search(args):
    """Preview metadata lookup (dry run)."""
    parsed = parse_title(args.title)

    table = Table(title="\n Title Parse", show_header=True, header_style="bold cyan")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Raw", args.title)
    table.add_row("Artist", parsed.artist or "[dim]—[/]")
    table.add_row("Title", parsed.title or "[dim]—[/]")
    table.add_row("Confidence", f"{parsed.confidence:.0%}")
    console.print(table)

    if not args.no_tag and (parsed.artist or parsed.title):
        console.print()
        with console.status("[bold green]Looking up on MusicBrainz..."):
            meta = search_recording(parsed)
        if meta:
            table = Table(title="MusicBrainz Match", show_header=True, header_style="bold cyan")
            table.add_column("Field")
            table.add_column("Value")
            table.add_row("Title", meta.title)
            table.add_row("Artist", meta.artist)
            table.add_row("Album", meta.album or "[dim]—[/]")
            table.add_row("Year", meta.year or "[dim]—[/]")
            table.add_row("Track #", meta.track_number or "[dim]—[/]")
            table.add_row("MBID", meta.musicbrainz_recording_id[:16] + "…" if meta.musicbrainz_recording_id else "[dim]—[/]")
            console.print(table)
        else:
            console.print("\n[yellow]No MusicBrainz match found.[/]")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="youtune",
        description="🎵 The smartest YouTube → MP3 downloader — auto-tag, album art, lyrics, Soulseek upgrades",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  youtune "https://youtube.com/watch?v=dQw4w9WgXcQ"
  youtune "https://youtube.com/watch?v=..." -o ~/Music --lyrics
  youtune "https://youtube.com/playlist?list=..." --normalize --soulseek
  youtune search "Rick Astley - Never Gonna Give You Up"
  youtune login          # connect your Soulseek account
  youtune status         # check connection & settings
""",
    )
    parser.add_argument("--version", action="version", version=f"youtune {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug output")

    sub = parser.add_subparsers(dest="command")

    # ── login ──
    sub.add_parser("login", help="Connect your Soulseek account")

    # ── status ──
    sub.add_parser("status", help="Show connection status & settings")

    # ── download ──
    dl = sub.add_parser("download", help="Download & tag a YouTube URL")
    dl.add_argument("url", help="YouTube video or playlist URL")
    dl.add_argument("-o", "--output", default="~/Downloads", help="Output directory (default: ~/Downloads)")
    dl.add_argument("-q", "--quality", type=int, default=0, help="Audio quality 0 (best) – 9 (worst)")
    dl.add_argument("--normalize", action="store_true", help="Apply EBU R128 loudness normalization")
    dl.add_argument("--lyrics", action="store_true", help="Fetch & embed lyrics")
    dl.add_argument("--no-tag", action="store_true", help="Skip MusicBrainz tagging")
    dl.add_argument("--no-art", action="store_true", help="Skip cover art")
    dl.add_argument("--no-rename", action="store_true", help="Keep original filename")

    g = dl.add_argument_group("Soulseek upgrade")
    g.add_argument("--soulseek", action="store_true", help="Search Soulseek for better quality")
    g.add_argument("--soulseek-user", help="Soulseek username (or run: youtune login)")
    g.add_argument("--soulseek-pass", help="Soulseek password (or run: youtune login)")
    g.add_argument("--prefer-flac", action="store_true", default=True, help="Prefer FLAC from Soulseek")
    g.add_argument("--min-bitrate", type=int, default=256, help="Min Soulseek bitrate (default: 256)")
    g.add_argument("--keep-youtube", action="store_true", help="Keep YouTube file on Soulseek upgrade")

    # ── search ──
    sr = sub.add_parser("search", help="Preview metadata for a title (dry run)")
    sr.add_argument("title", help='Video title (e.g. "Rick Astley - Never Gonna Give You Up")')
    sr.add_argument("--no-tag", action="store_true")

    args = parser.parse_args()
    _setup_logging(args.verbose)

    # Allow bare URL without "download" subcommand
    if not args.command:
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            sys.argv.insert(1, "download")
            args = parser.parse_args()
            _setup_logging(args.verbose)
        else:
            parser.print_help()
            sys.exit(0)

    try:
        if args.command == "login":
            cmd_login(args)
        elif args.command == "status":
            cmd_status(args)
        elif args.command == "download":
            cmd_download(args)
        elif args.command == "search":
            cmd_search(args)
    except FileNotFoundError as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        sys.exit(130)


if __name__ == "__main__":
    main()
