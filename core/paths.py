"""Project resource paths.

Everything is resolved from the project folder (the folder that contains
app.py), never from the current working directory.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER_IMAGE = str(PROJECT_ROOT / "assets" / "album_covers" / "placeholder.png")
AUDIO_FOLDER = str(PROJECT_ROOT / "audio")
ALBUM_CACHE = str(PROJECT_ROOT / "album_covers")
ASSETS_FOLDER = str(PROJECT_ROOT / "assets")

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
