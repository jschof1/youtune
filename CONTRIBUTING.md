# Contributing to youtune

Thanks for your interest! Here's how to get started:

## Setup

```bash
git clone https://github.com/jschof1/youtune.git
cd youtune
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

## Making changes

1. Create a branch: `git checkout -b my-feature`
2. Make your changes
3. Add tests if applicable
4. Run `pytest tests/ -v`
5. Submit a pull request

## Ideas for contributions

- 🎵 AcoustID fingerprinting (`--fingerprint`) for more accurate matching
- 🎵 Genre tagging from MusicBrainz tags
- 📊 Bitrate/quality reporting after download
- 🔄 Watch mode — monitor a YouTube playlist and auto-download new tracks
- 🎨 More title parsing patterns for different languages/formats
- 📦 Homebrew formula
- 📦 AUR package

## Reporting issues

Please include:
- Your OS and Python version
- The full command you ran
- The output (use `-v` for debug logs)
