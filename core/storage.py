"""Saving and loading user data (playlists + settings) as a versioned JSON file.

File location (Windows): %APPDATA%\\Custom Spotify Replica\\library.json
The file is written atomically (temp file + rename) so a crash or power cut
while saving can't leave a half-written file. If the file is unreadable it is
renamed to library.corrupt-<timestamp>.json and the app starts with defaults,
so the user's data is never silently thrown away.
"""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import List

from .paths import AUDIO_FOLDER, to_stored_path, from_stored_path

APP_DIR_NAME = "Custom Spotify Replica"
SCHEMA_VERSION = 1
DATA_FILE_NAME = "library.json"


def default_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_DIR_NAME)


@dataclass
class StoredPlaylist:
    name: str
    tracks: List[str] = field(default_factory=list)  # absolute file paths


@dataclass
class UserData:
    volume: int = 80
    muted: bool = False
    music_folders: List[str] = field(default_factory=lambda: [AUDIO_FOLDER])
    playlists: List[StoredPlaylist] = field(default_factory=list)
    is_new: bool = True        # True when no save file existed yet (first run)
    load_warning: str = ""     # message for the user if the file had to be reset


class Storage:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or default_data_dir()
        self.path = os.path.join(self.data_dir, DATA_FILE_NAME)

    # ------------------------------------------------------------------
    def load(self) -> UserData:
        if not os.path.exists(self.path):
            return UserData()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return self._from_dict(raw)
        except Exception as e:
            backup = self._quarantine()
            data = UserData()
            data.is_new = False
            data.load_warning = (
                f"Your saved library could not be read ({e}). "
                f"A copy was kept at {backup} and defaults were loaded."
            )
            print(data.load_warning)
            return data

    def save(self, data: UserData) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "settings": {
                "volume": int(data.volume),
                "muted": bool(data.muted),
                "music_folders": [to_stored_path(p) for p in data.music_folders],
            },
            "playlists": [
                {"name": p.name, "tracks": [to_stored_path(t) for t in p.tracks]}
                for p in data.playlists
            ],
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------
    def _from_dict(self, raw) -> UserData:
        if not isinstance(raw, dict):
            raise ValueError("unexpected file format")
        version = raw.get("version", 1)
        if version > SCHEMA_VERSION:
            raise ValueError(f"file was saved by a newer version of the app (v{version})")

        settings = raw.get("settings", {}) or {}
        data = UserData(is_new=False)
        data.volume = max(0, min(100, int(settings.get("volume", data.volume))))
        data.muted = bool(settings.get("muted", False))
        folders = settings.get("music_folders")
        if isinstance(folders, list):
            data.music_folders = [from_stored_path(str(p)) for p in folders]

        playlists = []
        for item in raw.get("playlists", []) or []:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            tracks = [from_stored_path(str(t)) for t in item.get("tracks", []) or []]
            playlists.append(StoredPlaylist(name, tracks))
        data.playlists = playlists
        return data

    def _quarantine(self) -> str:
        backup = os.path.join(self.data_dir, f"library.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json")
        try:
            os.replace(self.path, backup)
        except OSError:
            backup = self.path
        return backup
