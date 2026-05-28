# Changelog

All notable changes to youtune will be documented in this file.

## [1.2.2] - 2026-05-28

### Changed
- Hardened CLI argument validation and config-backed defaults.
- Improved yt-dlp subprocess error handling, timeout behavior, and downloaded-file detection.
- Fixed first-time ID3 tag creation for untagged MP3s.
- Updated package metadata for current setuptools standards.
- Expanded CI to test Python 3.9 through 3.13 and validate built packages.
- Updated installation docs for modern pip, pipx, and ffmpeg setup.

## [1.0.0] - 2025-04-15

### Added
- Smart YouTube title parsing (strips "Official Video [HD]" etc.)
- MusicBrainz auto-tagging (artist, album, year, track number)
- Cover art embedding from Cover Art Archive
- Lyrics embedding from lrclib
- Soulseek quality upgrade (FLAC / 320kbps)
- EBU R128 loudness normalization
- Playlist support
- Smart file renaming
- Dry-run metadata search (`youtune search`)
- Rich CLI output with progress spinners
- Cross-platform (macOS, Linux, Windows)
