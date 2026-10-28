"""Saving and loading user data (playlists + settings) as a versioned JSON file.

File location (Windows): %APPDATA%\\Sevbify\\library.json
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
from typing import Any, Dict, List

from .paths import AUDIO_FOLDER, to_stored_path, from_stored_path

APP_DIR_NAME = "Sevbify"
# Folders used under the app's earlier names; data is copied from the newest one once.
LEGACY_APP_DIR_NAMES = ["Aurvo", "Custom Spotify Replica"]  # newest first
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


def migrate_legacy_data(new_dir: str) -> bool:
    """Copy playlists/settings saved under the app's old name into new_dir.

    Runs only if new_dir has no library.json yet. The old folder is left in
    place as a backup. Returns True if something was copied.
    """
    import shutil
    if os.path.exists(os.path.join(new_dir, DATA_FILE_NAME)):
        return False
    parent = os.path.dirname(new_dir)
    for old_name in LEGACY_APP_DIR_NAMES:
        old_dir = os.path.join(parent, old_name)
        old_file = os.path.join(old_dir, DATA_FILE_NAME)
        if os.path.isfile(old_file):
            os.makedirs(new_dir, exist_ok=True)
            shutil.copy2(old_file, os.path.join(new_dir, DATA_FILE_NAME))
            return True
    return False


@dataclass
class StoredPlaylist:
    name: str
    # Each entry is either an absolute file path (str) or, for a song that is
    # not on this computer yet, a dict like {"pending": {"title":..., "artist":...}}.
    tracks: List[Any] = field(default_factory=list)
    folder: str = ""             # Your Library folder ("" = none)
    created: float = 0.0
    last_played: float = 0.0
    cover: str = ""              # custom cover picture


@dataclass
class UserData:
    volume: int = 80
    muted: bool = False
    music_folders: List[str] = field(default_factory=lambda: [AUDIO_FOLDER])
    playlists: List[StoredPlaylist] = field(default_factory=list)
    shuffle: bool = False
    repeat: str = "off"                 # "off" | "all" | "one"
    right_panel: str = "nowplaying"     # "" | "queue" | "nowplaying"
    online_enabled: bool = True         # Settings -> Online features
    lastfm_api_key: str = ""
    jamendo_client_id: str = ""
    download_source: str = "Bandcamp + YouTube"   # Settings -> Downloads (see core/downloader.SOURCES)
    download_notice_accepted: bool = False        # the one-time notice about downloading/streaming
    stream_full: bool = True                      # Settings: play full songs you don't have (else previews)
    download_folder: str = ""                     # Settings: where downloads go ("" = automatic)
    use_browser_cookies: bool = False             # Settings: let YouTube downloads use Chrome's sign-in
    playlist_files: bool = True                   # Settings: keep .m3u8 playlist files next to downloads
    folders: List[str] = field(default_factory=list)   # Your Library folders, in order
    library_sort: str = "recents"                 # "recents" | "added" | "alpha"
    library_view: str = "list"                    # "list" | "compact" | "grid"
    library_collapsed: bool = False               # Your Library shrunk to a strip of covers
    explicit_ok: bool = True   # Settings: allow songs marked explicit (online results)
    autoplay: bool = True   # Settings: keep playing similar songs when the queue ends
    fade_seconds: int = 0   # Settings: fade out/in between songs (0 = off)
    normalize: bool = False   # Settings: same loudness for every song (needs restart)
    eq_enabled: bool = False   # Settings: equaliser on
    eq_preset: str = 'Flat'   # equaliser preset name (or 'Custom')
    eq_bands: List[float] = field(default_factory=lambda: [0.0] * 10)   # 10 values in dB (-20..20)
    np_on_play: bool = True   # Settings: open the Now playing panel when you play
    notify_track: bool = False   # Settings: desktop notification when the song changes
    canvas_enabled: bool = True   # Settings: Canvas loop videos
    zoom: int = 100   # Settings: zoom level in % (applies after restart)
    startup: str = 'no'   # Settings: open after login (Windows)
    close_to_tray: bool = False   # Settings: close button minimises to the tray
    proxy_mode: str = 'auto'   # Settings: proxy (applies after restart)
    proxy_url: str = ''   # e.g. http://127.0.0.1:8080
    hw_accel: bool = True   # Settings: hardware acceleration (applies after restart)
    auto_update_check: bool = True   # Settings: check GitHub once a day for a new Sevbify / yt-dlp
    last_update_check: float = 0.0
    disabled_folders: List[str] = field(default_factory=list)   # music folders switched off in Settings
    recent: List[str] = field(default_factory=list)       # recently played file paths
    save_for_later: Dict[str, list] = field(default_factory=dict)  # genre -> [song dicts]
    shows: List[dict] = field(default_factory=list)       # followed podcasts / YouTube channels (Show dicts)
    books: List[dict] = field(default_factory=list)       # audiobooks in Your Library (Book dicts)
    resume: Dict[str, dict] = field(default_factory=dict) # episode / chapter key -> {"ms", "t", "track", "show"}
    finished: List[str] = field(default_factory=list)     # episode / chapter keys listened to the end
    offline: Dict[str, str] = field(default_factory=dict) # episode / chapter key -> downloaded file
    offline_info: Dict[str, dict] = field(default_factory=dict)  # same keys -> {"track", "show", "book", "t"}
    is_new: bool = True        # True when no save file existed yet (first run)
    load_warning: str = ""     # message for the user if the file had to be reset


def _bands(value):
    """Ten equaliser values in dB, clamped to VLC's range."""
    out = [0.0] * 10
    if isinstance(value, list):
        for i, v in enumerate(value[:10]):
            out[i] = max(-20.0, min(20.0, float(v)))
    return out


def _store_track(t):
    if isinstance(t, dict):
        return t
    return to_stored_path(t)


def _load_track(t):
    if isinstance(t, dict):
        return t if isinstance(t.get("pending"), dict) else None
    return from_stored_path(str(t))


class Storage:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or default_data_dir()
        if data_dir is None:
            try:
                migrate_legacy_data(self.data_dir)
            except OSError as e:
                print(f"Could not copy data from the old app folder: {e}")
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
                "shuffle": bool(data.shuffle),
                "repeat": data.repeat if data.repeat in ("off", "all", "one") else "off",
                "right_panel": data.right_panel,
                "online_enabled": bool(data.online_enabled),
                "lastfm_api_key": data.lastfm_api_key,
                "jamendo_client_id": data.jamendo_client_id,
                "download_source": data.download_source,
                "download_notice_accepted": bool(data.download_notice_accepted),
                "stream_full": bool(data.stream_full),
                "download_folder": to_stored_path(data.download_folder) if data.download_folder else "",
                "use_browser_cookies": bool(data.use_browser_cookies),
                "playlist_files": bool(data.playlist_files),
                "folders": list(data.folders),
                "library_sort": data.library_sort,
                "library_view": data.library_view,
                "library_collapsed": bool(data.library_collapsed),
                "explicit_ok": data.explicit_ok,
                "autoplay": data.autoplay,
                "fade_seconds": data.fade_seconds,
                "normalize": data.normalize,
                "eq_enabled": data.eq_enabled,
                "eq_preset": data.eq_preset,
                "eq_bands": list(data.eq_bands),
                "np_on_play": data.np_on_play,
                "notify_track": data.notify_track,
                "canvas_enabled": data.canvas_enabled,
                "zoom": data.zoom,
                "startup": data.startup,
                "close_to_tray": data.close_to_tray,
                "proxy_mode": data.proxy_mode,
                "proxy_url": data.proxy_url,
                "hw_accel": data.hw_accel,
                "auto_update_check": bool(data.auto_update_check),
                "last_update_check": float(data.last_update_check or 0),
                "disabled_folders": [to_stored_path(p) for p in data.disabled_folders],
            },
            "playlists": [
                {"name": p.name, "tracks": [_store_track(t) for t in p.tracks],
                 **({"folder": p.folder} if p.folder else {}),
                 **({"created": round(p.created, 3)} if p.created else {}),
                 **({"last_played": round(p.last_played, 3)} if p.last_played else {}),
                 **({"cover": to_stored_path(p.cover)} if p.cover else {})}
                for p in data.playlists
            ],
            "recent": [to_stored_path(t) for t in data.recent],
            "save_for_later": data.save_for_later,
            "shows": data.shows,
            "books": data.books,
            "resume": data.resume,
            "finished": data.finished[-2000:],
            "offline": {k: to_stored_path(v) for k, v in data.offline.items()},
            "offline_info": {k: v for k, v in data.offline_info.items() if k in data.offline},
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
        data.shuffle = bool(settings.get("shuffle", False))
        data.repeat = settings.get("repeat", "off") if settings.get("repeat") in ("off", "all", "one") else "off"
        data.right_panel = settings.get("right_panel", "") if settings.get("right_panel") in ("", "queue", "nowplaying") else ""
        data.online_enabled = bool(settings.get("online_enabled", True))
        data.lastfm_api_key = str(settings.get("lastfm_api_key", "") or "")
        data.jamendo_client_id = str(settings.get("jamendo_client_id", "") or "")
        if settings.get("download_source") in ("Bandcamp + YouTube", "Bandcamp only", "YouTube only"):
            data.download_source = settings["download_source"]
        data.download_notice_accepted = bool(settings.get("download_notice_accepted", False))
        data.stream_full = bool(settings.get("stream_full", True))
        folder = settings.get("download_folder") or ""
        data.download_folder = from_stored_path(folder) if folder else ""
        data.use_browser_cookies = bool(settings.get("use_browser_cookies", False))
        data.playlist_files = bool(settings.get("playlist_files", True))
        data.folders = [str(f) for f in settings.get("folders", []) or [] if str(f).strip()]
        data.library_sort = settings.get("library_sort") if settings.get("library_sort") in ("recents", "added", "alpha") \
            else "recents"
        data.library_view = settings.get("library_view") if settings.get("library_view") in ("list", "compact", "grid") \
            else "list"
        data.library_collapsed = bool(settings.get("library_collapsed", False))
        try:
            data.explicit_ok = bool(settings.get('explicit_ok', True))
        except (TypeError, ValueError):
            pass
        try:
            data.autoplay = bool(settings.get('autoplay', True))
        except (TypeError, ValueError):
            pass
        try:
            data.fade_seconds = max(0, min(12, int(settings.get('fade_seconds', 0) or 0)))
        except (TypeError, ValueError):
            pass
        try:
            data.normalize = bool(settings.get('normalize', False))
        except (TypeError, ValueError):
            pass
        try:
            data.eq_enabled = bool(settings.get('eq_enabled', False))
        except (TypeError, ValueError):
            pass
        try:
            data.eq_preset = str(settings.get('eq_preset', 'Flat') or 'Flat')
        except (TypeError, ValueError):
            pass
        try:
            data.eq_bands = _bands(settings.get('eq_bands'))
        except (TypeError, ValueError):
            pass
        try:
            data.np_on_play = bool(settings.get('np_on_play', True))
        except (TypeError, ValueError):
            pass
        try:
            data.notify_track = bool(settings.get('notify_track', False))
        except (TypeError, ValueError):
            pass
        try:
            data.canvas_enabled = bool(settings.get('canvas_enabled', True))
        except (TypeError, ValueError):
            pass
        try:
            data.zoom = int(settings.get('zoom', 100)) if int(settings.get('zoom', 100) or 100) in (70, 80, 90, 100, 110, 120, 130) else 100
        except (TypeError, ValueError):
            pass
        try:
            data.startup = settings.get('startup') if settings.get('startup') in ('no', 'yes', 'minimized') else 'no'
        except (TypeError, ValueError):
            pass
        try:
            data.close_to_tray = bool(settings.get('close_to_tray', False))
        except (TypeError, ValueError):
            pass
        try:
            data.proxy_mode = settings.get('proxy_mode') if settings.get('proxy_mode') in ('auto', 'none', 'http') else 'auto'
        except (TypeError, ValueError):
            pass
        try:
            data.proxy_url = str(settings.get('proxy_url', '') or '')
        except (TypeError, ValueError):
            pass
        try:
            data.hw_accel = bool(settings.get('hw_accel', True))
            data.auto_update_check = bool(settings.get("auto_update_check", True))
            try:
                data.last_update_check = float(settings.get("last_update_check") or 0)
            except (TypeError, ValueError):
                data.last_update_check = 0.0
        except (TypeError, ValueError):
            pass
        try:
            data.disabled_folders = [from_stored_path(str(p)) for p in settings.get('disabled_folders', []) or []]
        except (TypeError, ValueError):
            pass
        data.recent = [from_stored_path(str(t)) for t in raw.get("recent", []) or [] if isinstance(t, str)]
        data.shows = [d for d in raw.get("shows", []) or [] if isinstance(d, dict) and (d.get("feed_url") or d.get("apple_id"))]
        data.books = [d for d in raw.get("books", []) or [] if isinstance(d, dict) and d.get("identifier")]
        resume = raw.get("resume", {}) or {}
        data.resume = {str(k): v for k, v in resume.items() if isinstance(v, dict) and "ms" in v} \
            if isinstance(resume, dict) else {}
        data.finished = [str(k) for k in raw.get("finished", []) or []]
        offline = raw.get("offline", {}) or {}
        data.offline = {str(k): from_stored_path(str(v)) for k, v in offline.items()} if isinstance(offline, dict) else {}
        info = raw.get("offline_info", {}) or {}
        data.offline_info = {str(k): v for k, v in info.items() if isinstance(v, dict) and isinstance(v.get("track"), dict)} \
            if isinstance(info, dict) else {}
        sfl = raw.get("save_for_later", {}) or {}
        data.save_for_later = {str(k): list(v) for k, v in sfl.items() if isinstance(v, list)} if isinstance(sfl, dict) else {}

        playlists = []
        for item in raw.get("playlists", []) or []:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            tracks = [_load_track(t) for t in item.get("tracks", []) or []]
            tracks = [t for t in tracks if t is not None]
            def num(key):
                try:
                    return float(item.get(key) or 0)
                except (TypeError, ValueError):
                    return 0.0
            folder = str(item.get("folder") or "")
            cover = item.get("cover") or ""
            playlists.append(StoredPlaylist(name, tracks, folder if folder in data.folders else "",
                                            num("created"), num("last_played"),
                                            from_stored_path(str(cover)) if cover else ""))
        data.playlists = playlists
        return data

    def _quarantine(self) -> str:
        backup = os.path.join(self.data_dir, f"library.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json")
        try:
            os.replace(self.path, backup)
        except OSError:
            backup = self.path
        return backup
