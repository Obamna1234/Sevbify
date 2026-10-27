"""Find a full-length stream for a song you don't have yet, with SEVBY's matching (no UI code).

Used when an online song (from Search or Radio) is played and Settings -> "Songs you don't have" is set to
"Full song": look on Bandcamp first, then YouTube (the same choice SEVBY makes when downloading), pick the
best match using the song's real length, and ask yt-dlp for a direct audio link that VLC can play. Nothing is
saved; the song stays "not downloaded" until you download it.

Streaming YouTube audio this way skips YouTube's own player (and its ads), which goes against YouTube's terms
of service, like downloading does. Sevbify shows this once, the first time, and the user decides.
"""
import threading
import time

from core import downloader

CACHE_SECONDS = 30 * 60          # direct links from YouTube expire after a few hours; stay well inside that
_cache = {}
_lock = threading.Lock()


class NoFullSong(Exception):
    """No full-length version could be found (the preview is used instead)."""


def _pick_youtube(e, line, duration_s):
    meta = dict(e.meta_for(line))
    if duration_s:
        meta["duration"] = duration_s
    ranked = e.rank_youtube_results(e.search_youtube_candidates(line, 8), line, meta)
    words = set(e._words(meta.get("title") or e._split_query(line)[1]))
    if words:   # same rule as the downloader: the video title must contain most of the song title's words
        ranked = [(sc, en) for sc, en in ranked if len(words & set(e._words(en.get("title") or ""))) / len(words) >= 0.5]
    if not ranked:
        return None
    entry = ranked[0][1]
    url = entry.get("url") or ""
    return url if url.startswith("http") else f"https://www.youtube.com/watch?v={entry.get('id')}"


def _extract(e, page):
    """Direct audio link (+ the HTTP headers it needs) for a Bandcamp or YouTube page, without downloading."""
    if e.yt_dlp is None:
        raise NoFullSong("yt-dlp is not installed")
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True,
            "format": "bestaudio/best", "socket_timeout": 20, "skip_download": True}
    with e.yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(page, download=False)
    url = (info or {}).get("url")
    if not url:
        raise NoFullSong("no playable audio link")
    return url, dict(info.get("http_headers") or {}), info.get("duration") or 0


def find_full_song(artist, title, duration_ms=0, source=downloader.SOURCE_BOTH, extract=None):
    """Return {"url", "headers", "page", "source", "duration_ms"} for a full-length stream, or raise NoFullSong."""
    line = downloader.song_line(artist, title)
    key = (line.casefold(), source)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return dict(hit[1])
    e = downloader.engine()
    extract = extract or (lambda page: _extract(e, page))
    candidates = []
    if source != downloader.SOURCE_YOUTUBE:
        try:
            bc = e.search_bandcamp(line)
        except Exception:
            bc = {}
        if bc.get("found") and bc.get("url"):
            candidates.append(("Bandcamp", bc["url"]))
    if source != downloader.SOURCE_BANDCAMP:
        try:
            yt = _pick_youtube(e, line, int((duration_ms or 0) / 1000))
        except Exception:
            yt = None
        if yt:
            candidates.append(("YouTube", yt))
    last = None
    for name, page in candidates:
        try:
            url, headers, seconds = extract(page)
        except Exception as exc:              # e.g. a Bandcamp track that isn't streamable: try YouTube
            last = exc
            continue
        result = {"url": url, "headers": headers, "page": page, "source": name,
                  "duration_ms": int((seconds or 0) * 1000)}
        with _lock:
            _cache[key] = (time.time(), dict(result))
        return result
    raise NoFullSong(str(last) if last else "not found on Bandcamp or YouTube")


def clear_cache():
    with _lock:
        _cache.clear()
