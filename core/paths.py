"""Project resource paths.

Everything is resolved from the project folder (the folder that contains
app.py), never from the current working directory.
"""
import os
from pathlib import Path
import sys

# True when running as the packaged "Sevbify.exe" (built by PyInstaller).
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # PROJECT_ROOT = folder containing the .exe; bundled read-only files
    # (artwork, placeholder) live in PyInstaller's _internal folder.
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    RESOURCE_ROOT = PROJECT_ROOT


# The Android app (and tests) can point Sevbify's data somewhere else with SEVBIFY_DATA_DIR.
DATA_DIR_OVERRIDE = os.environ.get("SEVBIFY_DATA_DIR", "")


def _user_data_dir() -> Path:
    # Same location as core.storage.default_data_dir() (kept here to avoid an import cycle).
    if DATA_DIR_OVERRIDE:
        return Path(DATA_DIR_OVERRIDE)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "Sevbify"


PLACEHOLDER_IMAGE = str(RESOURCE_ROOT / "assets" / "album_covers" / "placeholder.png")
ASSETS_FOLDER = str(RESOURCE_ROOT / "assets")

# Default music folder: an "audio" folder next to app.py / the .exe if there is
# one, otherwise the user's Windows "Music" folder. More folders can be added
# in the app (Your Library -> Add folder).
_local_audio = PROJECT_ROOT / "audio"
AUDIO_FOLDER = str(_local_audio if _local_audio.is_dir() else Path.home() / "Music")

# Generated artwork cache. The packaged app may live in a read-only folder
# (e.g. Program Files), so it keeps its cache in the user's app-data folder.
ALBUM_CACHE = str(_user_data_dir() / "album_covers" if (FROZEN or DATA_DIR_OVERRIDE) else PROJECT_ROOT / "album_covers")

os.makedirs(ALBUM_CACHE, exist_ok=True)


def normalise_path(path: str) -> str:
    """Canonical form of a file path, used to compare/identify tracks.

    On Windows this is case-insensitive and uses backslashes, so the same file
    is never treated as two different tracks.
    """
    return os.path.normcase(os.path.abspath(str(path)))


def to_stored_path(path: str) -> str:
    """Path as written to the save file.

    Files inside the project folder are stored relative to it, so playlists
    keep working if the whole project folder is moved or renamed.
    """
    abs_path = os.path.abspath(str(path))
    try:
        rel = os.path.relpath(abs_path, PROJECT_ROOT)
    except ValueError:  # different drive on Windows
        return abs_path
    if rel.startswith(".."):
        return abs_path
    return rel.replace("\\", "/")


def from_stored_path(stored: str) -> str:
    """Inverse of to_stored_path."""
    if os.path.isabs(stored):
        return stored
    return str(PROJECT_ROOT / stored)
