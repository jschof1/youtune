"""Configuration management — save/load prefs from ~/.youtune/config.json"""

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".youtune"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "soulseek_user": "",
    "soulseek_pass": "",
    "output_dir": "~/Downloads",
    "quality": 0,
    "normalize": False,
    "lyrics": False,
    "prefer_flac": True,
    "min_bitrate": 256,
}


def load_config() -> dict:
    """Load config from disk, merged with defaults."""
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            config.update(saved)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Config file corrupt, using defaults: %s", e)
    return config


def save_config(config: dict):
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Only save non-default values to keep the file clean
    to_save = {}
    defaults = dict(DEFAULTS)
    for key, value in config.items():
        if key in defaults and value != defaults[key]:
            to_save[key] = value
        elif key not in defaults:
            to_save[key] = value

    with open(CONFIG_FILE, "w") as f:
        json.dump(to_save, f, indent=2)
    log.info("Config saved to %s", CONFIG_FILE)


def get_soulseek_creds(config: dict) -> tuple[Optional[str], Optional[str]]:
    """Get Soulseek credentials from config."""
    user = config.get("soulseek_user", "")
    pas = config.get("soulseek_pass", "")
    if user and pas:
        return user, pas
    return None, None
