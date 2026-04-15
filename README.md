<div align="center">

# 🎵 youtune

**The smartest YouTube → MP3 downloader**

[![PyPI](https://img.shields.io/pypi/v/youtune?color=blue&label=pip%20install%20youtune)](https://pypi.org/project/youtune/)
[![Python](https://img.shields.io/pypi/pyversions/youtune)](https://pypi.org/project/youtune/)
[![Tests](https://github.com/jschof1/youtune/actions/workflows/ci.yml/badge.svg)](https://github.com/jschof1/youtune/actions)
[![License: MIT](https://img.shields.io/github/license/jschof1/youtune)](LICENSE)
[![Stars](https://img.shields.io/github/stars/jschof1/youtune?style=social)](https://github.com/jschof1/youtune/stargazers)

*Auto-tags with MusicBrainz · Embeds album art · Fetches lyrics ·*
*Upgrades quality via Soulseek · Normalizes loudness · Smart renaming*

</div>

---

**One command. Perfect MP3.**

```bash
pip install youtune
youtune "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

```
  ╭──────────────────────────────────╮
  │  youtune v1.0.0                  │
  │  The smartest YouTube → MP3 downloader │
  ╰──────────────────────────────────╯

  🎵 Rick Astley — Never Gonna Give You Up (confidence: 90%)
  ✅ Metadata found via MusicBrainz
     📀 Album: Whenever You Need Somebody
     📅 Year:  1987
     #️⃣  Track: 1
  📝 Lyrics found (36 lines)
  🖼️  Cover art embedded
  📝 Renamed → Rick Astley - Never Gonna Give You Up.mp3

  ✨ Done!
```

## The problem

`yt-dlp -x --audio-format mp3 "https://youtube.com/watch?v=..."` gives you:

- ❌ Filename: `Rick Astley - Never Gonna Give You Up (Official Music Video) [HD Remaster].mp3`
- ❌ No artist, album, year, or track number
- ❌ No album art
- ❌ No lyrics
- ❌ 128kbps YouTube audio, no loudness normalization
- ❌ Messy filenames with junk like "(Official Video)", "[HD]", etc.

**youtune** fixes *all* of that — automatically.

## Features

| | Feature | What it does |
|---|---|---|
| 🧠 | **Smart title parsing** | Strips "Official Music Video [HD Remaster]" → extracts clean artist + song |
| 🏷️ | **MusicBrainz tagging** | Looks up the real recording → writes ID3v2 tags (artist, album, year, track #, genre) |
| 🖼️ | **Album art** | Fetches cover from [Cover Art Archive](https://coverartarchive.org/) → embeds in MP3 |
| 📝 | **Lyrics** | Fetches synced/plaintext lyrics from [lrclib](https://lrclib.net/) → embeds in file |
| 🔥 | **Soulseek upgrade** | Searches [Soulseek](https://www.soulseekqt.net/) for FLAC/320kbps → replaces YouTube download |
| 🔊 | **Loudness normalization** | EBU R128 normalization — no more quiet/blasting tracks |
| 📂 | **Playlists** | Download + tag entire playlists in one shot |
| ✏️ | **Smart renaming** | `Rick Astley - Never Gonna Give You Up.mp3` not `vevo_aU_official(1).mp3` |
| 🔎 | **Dry-run search** | `youtune search "Artist - Song"` → preview metadata without downloading |
| 🌍 | **Thousands of sites** | Works with any site [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) — not just YouTube |

## Install

```bash
pip install youtune
```

**Prerequisites:** [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/) must be on your PATH:

```bash
# macOS
brew install yt-dlp ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg && pip install yt-dlp

# Windows (winget)
winget install yt-dlp.yt-dlp Gyan.FFmpeg

# Arch
sudo pacman -S yt-dlp ffmpeg
```

### Optional: Soulseek support

```bash
pip install youtune[soulseek]
```

## Usage

### Download & auto-tag a track

```bash
youtune "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

### Download with lyrics + loudness normalization

```bash
youtune "https://youtube.com/watch?v=..." --lyrics --normalize
```

### Download a playlist

```bash
youtune "https://youtube.com/playlist?list=PL..." -o ~/Music/Playlist
```

### Upgrade quality via Soulseek

```bash
youtune "https://youtube.com/watch?v=..." \
  --soulseek \
  --soulseek-user myusername \
  --soulseek-pass mypassword
```

Downloads from YouTube first, then searches Soulseek for FLAC or 320kbps. If found, replaces the YouTube file.

### Preview metadata (no download)

```bash
youtune search "Radiohead - Everything In Its Right Place"
```

### Skip everything, just download

```bash
youtune "https://youtube.com/watch?v=..." --no-tag --no-art --no-rename
```

## How it works

```
  YouTube URL
      │
      ▼
  ┌────────────┐
  │  yt-dlp    │  Extract audio → MP3
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │  Parse      │  "Rick Astley - Never Gonna Give You Up (Official Video) [HD]"
  │  title      │  → artist: "Rick Astley", song: "Never Gonna Give You Up"
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │ MusicBrainz │  Lookup recording → album, year, track #, MBIDs
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │ Cover Art   │  Fetch from Cover Art Archive → embed in MP3
  │ Archive     │
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │  lrclib     │  Fetch synced lyrics → embed in MP3
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │  mutagen    │  Write ID3v2 tags + APIC art + USLT lyrics
  └─────┬──────┘
        │
        ▼
  ┌────────────┐
  │  Soulseek   │  (optional) Search for FLAC/320 → replace YouTube file
  └─────┬──────┘
        │
        ▼
  Artist - Title.mp3 ✨
  (clean, tagged, art, lyrics)
```

## All options

```
usage: youtune download [-h] [-o OUTPUT] [-q QUALITY] [--normalize] [--lyrics]
                        [--no-tag] [--no-art] [--no-rename] [--soulseek]
                        [--soulseek-user USER] [--soulseek-pass PASS]
                        [--prefer-flac] [--min-bitrate N] [--keep-youtube]
                        URL

  -o, --output         Output directory (default: .)
  -q, --quality        Audio quality 0 (best) – 9 (worst)
  --normalize          Apply EBU R128 loudness normalization
  --lyrics             Fetch & embed lyrics
  --no-tag             Skip MusicBrainz tagging
  --no-art             Skip cover art
  --no-rename          Keep original filename

  --soulseek           Search Soulseek for better quality
  --soulseek-user      Soulseek username
  --soulseek-pass      Soulseek password
  --prefer-flac        Prefer FLAC from Soulseek (default: true)
  --min-bitrate        Minimum Soulseek bitrate (default: 256)
  --keep-youtube       Keep YouTube file when Soulseek upgrades
```

## FAQ

<details>
<summary><strong>Does it work with Spotify / SoundCloud / Bandcamp?</strong></summary>

Yes! youtune works with any URL that [yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) — that's thousands of sites.

</details>

<details>
<summary><strong>What if MusicBrainz doesn't have the track?</strong></summary>

youtune falls back to the parsed YouTube title. You'll still get a clean filename and basic ID3 tags from whatever was parsed.

</details>

<details>
<summary><strong>What's the Soulseek upgrade?</strong></summary>

YouTube audio is typically 128kbps AAC. Soulseek is a P2P network where people share FLAC and 320kbps MP3s. If you enable `--soulseek`, youtune will search for and download a higher-quality version to replace the YouTube rip. Requires a free Soulseek account.

</details>

<details>
<summary><strong>Can I use it in scripts / CI?</strong></summary>

Yes — exit code 0 on success, non-zero on failure. Use `-v` for debug logging. No interactive prompts.

</details>

<details>
<summary><strong>Why not just use beets?</strong></summary>

[beets](https://beets.io/) is great for library management, but it's a heavy setup. youtune is zero-config — one command and you're done. You can pipe youtune output into beets if you want both.

</details>

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## Related projects

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — the download engine that makes this possible
- [MusicBrainz](https://musicbrainz.org/) — open music encyclopedia
- [Cover Art Archive](https://coverartarchive.org/) — free cover art API
- [lrclib](https://lrclib.net/) — open-source lyrics database
- [mutagen](https://github.com/quodlibet/mutagen) — Python audio metadata library
- [beets](https://beets.io/) — the music organizer for obsessives
- [slsk-batchdl](https://github.com/fiso64/slsk-batchdl) — Soulseek batch downloader

## License

[MIT](LICENSE)
