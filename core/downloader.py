"""Download songs into the library using the SEVBY engine (no UI code).

`run_download` takes a list of "Artist - Title" lines and, for each one, looks on Bandcamp first and falls back
to YouTube, saving a 128 kbps MP3 with tags and cover art (see core/sevby_engine.py).
It reports progress through plain callbacks so the window (or a test) can show it.

Only download music you have the right to download.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

SOURCE_BOTH = "Bandcamp + YouTube"
SOURCE_BANDCAMP = "Bandcamp only"
SOURCE_YOUTUBE = "YouTube only"
SOURCES = (SOURCE_BOTH, SOURCE_BANDCAMP, SOURCE_YOUTUBE)

_engine = None
ALLOW_BROWSER_COOKIES = False     # Settings: may YouTube downloads use the sign-in saved in Chrome? (private: no)


def engine():
    """The SEVBY engine module, imported the first time it is needed (it pulls in yt-dlp)."""
    global _engine
    if _engine is None:
        from core import sevby_engine
        _engine = sevby_engine
        try:
            _ensure_ffmpeg(_engine)
        except Exception as exc:  # never stop the app over this; check_tools() will report it
            print(f"Could not set up the bundled ffmpeg: {exc}")
        _respect_cookie_setting(_engine)
    return _engine


def _respect_cookie_setting(e):
    """SEVBY retries a blocked YouTube download with the sign-in cookies saved in Chrome. For privacy Sevbify
    only does that when Settings allows it (ALLOW_BROWSER_COOKIES); the engine reads this at call time."""
    original = e.download_youtube_mp3
    if getattr(original, "_sevbify_cookies", False):
        return

    def download_youtube_mp3(query, out_dir, log, use_cookies=True):
        return original(query, out_dir, log, use_cookies=use_cookies and ALLOW_BROWSER_COOKIES)

    download_youtube_mp3._sevbify_cookies = True
    e.download_youtube_mp3 = download_youtube_mp3


_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def artist_folder(artist: str) -> str:
    """Folder name for an artist: the main artist only, so "A feat. B", "A ft. B", "A featuring B", "A x B" and
    "A vs. B" all go under "A". Names that contain "&", "," or "/" are kept whole, because they are usually one
    band (Simon & Garfunkel, Earth, Wind & Fire, AC/DC); the search results already list the main artist alone.
    Safe for Windows file names."""
    import re
    main = re.split(r"\s+(?:feat\.?|ft\.?|featuring|x|vs\.?)\s+|\s*[\(\[](?:feat\.?|ft\.?|featuring)\b",
                    artist or "", maxsplit=1, flags=re.I)[0].strip()
    main = main.replace("/", "-")
    main = re.sub(r'[<>:"\\|?*]', "", main).strip(" .")[:80] or "Unknown Artist"
    if main.split(".")[0].upper() in _WINDOWS_RESERVED:      # "CON", "NUL", ... can't be folder names
        main += " (artist)"
    return main


def _ensure_ffmpeg(e, cache_dir=None):
    """When running from source (Run Sevbify.bat) most PCs have no ffmpeg. The imageio-ffmpeg package
    (in requirements.txt) contains one; copy it once as "ffmpeg(.exe)" into Sevbify's data folder and put
    that folder on PATH so the engine and yt-dlp find it. The packaged app bundles its own copy."""
    import shutil
    if os.path.isfile(e.ffmpeg_path()) or shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return
    if cache_dir is None:
        from core.storage import default_data_dir
        cache_dir = os.path.join(default_data_dir(), "ffmpeg")
    os.makedirs(cache_dir, exist_ok=True)
    dst = os.path.join(cache_dir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copy2(src, dst + ".tmp")
        os.replace(dst + ".tmp", dst)
    os.environ["PATH"] = cache_dir + os.pathsep + os.environ.get("PATH", "")


def default_download_folder(music_folders) -> str:
    """Where new downloads go: the first music folder the user has added."""
    for f in music_folders or []:
        if f:
            return str(f)
    return ""


def song_line(artist: str, title: str) -> str:
    """The "Artist - Title" line the engine searches for."""
    artist, title = (artist or "").strip(), (title or "").strip()
    return f"{artist} - {title}" if artist else title


def parse_lines(text: str) -> list:
    """Turn pasted text into a clean list of "Artist - Title" lines (also reads CSV exports)."""
    return engine().parse_song_lines(text or "")


def check_tools() -> list:
    """Problems that would stop downloads from working, as readable sentences (empty list = fine)."""
    e = engine()
    problems = []
    if not e.have_ytdlp():
        problems.append("yt-dlp is not installed, so nothing can be downloaded. Run: pip install yt-dlp")
    import shutil
    ff = e.ffmpeg_path()
    if not (os.path.isfile(ff) or shutil.which(ff)):
        problems.append("ffmpeg was not found. Install it (https://ffmpeg.org) or put ffmpeg next to the app.")
    return problems


class Controls:
    """Pause / stop switches shared with the worker thread (they are the engine's own flags)."""

    @staticmethod
    def reset():
        e = engine()
        e.STOP_EVENT.clear()
        e.PAUSE_EVENT.clear()

    @staticmethod
    def stop():
        engine().STOP_EVENT.set()

    @staticmethod
    def set_paused(on: bool):
        e = engine()
        (e.PAUSE_EVENT.set if on else e.PAUSE_EVENT.clear)()

    @staticmethod
    def is_paused() -> bool:
        return engine().PAUSE_EVENT.is_set()


def run_download(
    songs: list,
    out_dir: str,
    source: str = SOURCE_BOTH,
    *,
    log: Callable[[str], None] = lambda _m: None,
    on_start: Callable[[int, int, str], None] = lambda _i, _n, _s: None,
    on_step: Callable[[str], None] = lambda _t: None,
    on_result: Callable[[int, int, str, dict], None] = lambda _i, _n, _s, _r: None,
    process: Optional[Callable] = None,
) -> dict:
    """Download every song in `songs` into `out_dir`, one after another.

    Returns {"ok", "skip", "fail", "stopped", "paths", "failed"}: counts, whether Stop was pressed,
    the files that were saved, and the lines that failed (so they can be retried).
    `process` replaces the real per-song download (used by the tests).
    """
    e = engine()
    process = process or e.process_song
    os.makedirs(out_dir, exist_ok=True)
    opts = {
        "use_bc": source != SOURCE_YOUTUBE,
        "use_yt": source != SOURCE_BANDCAMP,
        "free": False,
    }
    e.QUALITY["best"] = False       # Sevbify saves plain 128 kbps MP3s
    e.QUALITY["free"] = False
    e.HQ_SONGS.clear()

    state: dict = {}
    result = {"ok": 0, "skip": 0, "fail": 0, "stopped": False, "paths": [], "failed": []}
    n = len(songs)
    for i, song in enumerate(songs, 1):
        while e.PAUSE_EVENT.is_set() and not e.STOP_EVENT.is_set():
            time.sleep(0.2)
        if e.STOP_EVENT.is_set():
            result["stopped"] = True
            break
        on_start(i, n, song)
        log("-" * 40)
        log(f"[{i}/{n}] {song}")
        try:
            res = process(song, out_dir, opts, state, log, on_step)
        except e._Stopped:
            res = {"status": "fail", "note": "stopped"}
        except Exception as exc:  # one bad song must never stop the rest
            log(f"  Unexpected error: {exc}")
            res = {"status": "fail", "note": "unexpected error"}
        if e.STOP_EVENT.is_set() and res.get("status") == "fail" and res.get("note") == "stopped":
            result["stopped"] = True
            break
        st = res.get("status")
        if st == "ok":
            result["ok"] += 1
            if res.get("path"):
                result["paths"].append(res["path"])
        elif st in ("skip", "dup"):
            result["skip"] += 1
        else:
            result["fail"] += 1
            result["failed"].append(song)
        on_result(i, n, song, res)
        if res.get("note"):
            log(f"  => {res['note']}")
    return result


def summary_text(res: dict) -> str:
    parts = [f"{res['ok']} downloaded"]
    if res["skip"]:
        parts.append(f"{res['skip']} already there")
    if res["fail"]:
        parts.append(f"{res['fail']} failed")
    text = " · ".join(parts)
    return ("Stopped · " if res["stopped"] else "Done · ") + text
