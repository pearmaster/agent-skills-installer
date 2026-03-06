"""Configuration management using TOML files stored in ~/.agent-skills-installer/."""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w

CONFIG_DIR = Path.home() / ".agent-skills-installer"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG: dict = {
    "install": {
        "last_destination": "",
        "recent_repos": [],
    },
}

MAX_RECENT_REPOS = 5


def load_config() -> dict:
    """Load config from disk, returning defaults if the file doesn't exist."""
    if not CONFIG_FILE.exists():
        return _deep_copy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        # Merge with defaults so new keys are always present
        return _merge(DEFAULT_CONFIG, data)
    except Exception:
        return _deep_copy(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """Write config to disk, creating the directory if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)


def get_last_destination(config: dict) -> str:
    """Return the last used destination path, or empty string."""
    return config.get("install", {}).get("last_destination", "")


def set_last_destination(config: dict, path: str) -> None:
    """Set the last used destination path."""
    config.setdefault("install", {})["last_destination"] = path


def get_recent_repos(config: dict) -> list[str]:
    """Return the list of recently used repo URLs (most recent first)."""
    return list(config.get("install", {}).get("recent_repos", []))


def add_recent_repo(config: dict, url: str) -> None:
    """Add a repo URL to the recent list, keeping at most MAX_RECENT_REPOS entries."""
    repos = get_recent_repos(config)
    # Remove if already present so it moves to the front
    if url in repos:
        repos.remove(url)
    repos.insert(0, url)
    repos = repos[:MAX_RECENT_REPOS]
    config.setdefault("install", {})["recent_repos"] = repos


# ── helpers ──────────────────────────────────────────────────────────


def _deep_copy(d: dict) -> dict:
    """Simple deep copy for nested dicts/lists of primitives."""
    import copy

    return copy.deepcopy(d)


def _merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into a copy of *defaults*."""
    result = _deep_copy(defaults)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result
