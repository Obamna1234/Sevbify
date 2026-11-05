"""Find a full-length stream for a song you don't have yet, with SEVBY's matching (no UI code).

Used when an online song (from Search or Radio) is played and Settings -> "Songs you don't have" is set to
"Full song": look on Bandcamp first, then YouTube (the same choice SEVBY makes when downloading), pick the
best match using the song's real length, and ask yt-dlp for a direct audio link that VLC can play. Nothing is
saved; the song stays "not downloaded" until you download it.

Streaming YouTube audio this way skips YouTube's own player (and its ads), which goes against YouTube's terms
of service, like downloading does. Sevbify shows this once, the first time, and the user decides.
"""
import json
import os
import threading
import time
import urllib.parse

from core import downloader

CACHE_SECONDS = 30 * 60          # direct links from YouTube expire after a few hours; stay well inside that
_cache = {}
_pages = {}                      # song -> the page it was found on (kept all session: finding it again skips the searches)
_inflight = {}                   # song -> a lookup already running (a second ask waits for it instead of repeating it)
_lock = threading.Lock()
_store_path = ""                 # where the found pages are kept between runs (set by the phone app)
_MAX_PAGES = 1500
_PAGE_HOSTS = ("youtube.com", "youtu.be", "bandcamp.com")


def _page_ok(name, page):
    """A remembered page is only trusted when it is an https page on YouTube or Bandcamp (the file is on disk)."""
    if name not in ("Bandcamp", "YouTube") or not isinstance(page, str):
        return False
    try:
        u = urllib.parse.urlparse(page)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in _PAGE_HOSTS)


def set_page_store(path):
    """Keep where each song was found (not the links: they expire) in `path`, so a song played before skips the
    searches even after the app was closed. Loads what is there."""
    global _store_path
    _store_path = path
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except (OSError, ValueError):
        return
    with _lock:
        for row in (rows if isinstance(rows, list) else [])[-_MAX_PAGES:]:
            if (isinstance(row, list) and len(row) == 4 and all(isinstance(x, str) for x in row)
                    and row[1] in (downloader.SOURCE_BOTH, downloader.SOURCE_BANDCAMP, downloader.SOURCE_YOUTUBE)
                    and _page_ok(row[2], row[3])):
                _pages[(row[0], row[1])] = (row[2], row[3])


def _save_pages():
    if not _store_path:
        return
    with _lock:
        rows = [[k[0], k[1], v[0], v[1]] for k, v in list(_pages.items())[-_MAX_PAGES:]]
    tmp = _store_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        os.replace(tmp, _store_path)
    except OSError:
        pass


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


_preferred_attempt = 0           # which of the attempts below worked last time (tried first from then on)


def _attempts(e):
    """The yt-dlp settings to try for a link, fastest first. On the phones yt-dlp is told to ask several YouTube
    clients, one after the other, which is slow; a single fast client usually works, so those go first and the
    full list is the fallback. Desktop (no override) has just the one attempt."""
    base = dict(e.yt_extractor_args() or {})
    clients = list((base.get("youtube") or {}).get("player_client") or [])
    if not clients:
        return [base]
    fast = [{"youtube": {**base["youtube"], "player_client": [c]}} for c in ("android_vr", "tv", "mweb") if c in clients]
    return fast + [base]


def url_works(url, headers=None, timeout=8):
    """Does this audio link actually give out data? A YouTube link can be extracted without trouble and still be
    refused (HTTP 403) when the player asks for it, depending on which YouTube client produced it. This asks for
    the first two bytes. False only when the server clearly refuses; if the check itself can't be done (no
    answer, odd reply) it says True and lets the player try."""
    import urllib.error
    import urllib.request
    if not str(url).startswith("https://"):
        return True
    try:
        req = urllib.request.Request(url, headers={**(headers or {}), "Range": "bytes=0-1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(2)
            return r.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code not in (400, 401, 403, 404, 410)
    except Exception:
        return True


def link_failed(url):
    """The player was refused this link: forget it, and start the next lookups with the next YouTube client."""
    global _preferred_attempt
    with _lock:
        for k in [k for k, v in _cache.items() if v[1].get("url") == url]:
            _cache.pop(k, None)
    n = len(_attempts(downloader.engine()))
    _preferred_attempt = (_preferred_attempt + 1) % max(n, 1)
    return True


def _extract(e, page):
    """Direct audio link (+ the HTTP headers it needs) for a Bandcamp or YouTube page, without downloading."""
    global _preferred_attempt
    if e.yt_dlp is None:
        raise NoFullSong("yt-dlp is not installed")
    attempts = _attempts(e)
    order = list(range(_preferred_attempt, len(attempts))) + list(range(0, min(_preferred_attempt, len(attempts))))
    last = None
    for i in order:
        opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True,
                "format": __import__("core.quality", fromlist=["x"]).STREAM_AUDIO_FORMAT,
                "socket_timeout": 15 if len(attempts) > 1 else 20,
                "skip_download": True, "allowed_extractors": e.SONG_EXTRACTORS, "extractor_args": attempts[i]}
        try:
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(page, download=False)
            url = (info or {}).get("url")
            if not url:
                raise NoFullSong("no playable audio link")
            headers = dict(info.get("http_headers") or {})
            if i != order[-1] and not url_works(url, headers):       # refused: this client's links don't play, try the next
                raise NoFullSong("the link was refused")
        except Exception as exc:
            last = exc
            continue
        _preferred_attempt = i
        return url, headers, info.get("duration") or 0
    raise last if last else NoFullSong("no playable audio link")


def find_full_song(artist, title, duration_ms=0, source=downloader.SOURCE_BOTH, extract=None):
    """Return {"url", "headers", "page", "source", "duration_ms", "timings"} for a full-length stream, or raise
    NoFullSong. `timings` says where the seconds went (for the Playback status log). The same song asked for twice
    at once (a prefetch and a tap) is looked up once."""
    line = downloader.song_line(artist, title)
    key = (line.casefold(), source)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return dict(hit[1])
        slot = _inflight.get(key)
        owner = slot is None
        if owner:
            slot = _inflight[key] = {"event": threading.Event(), "result": None, "error": None}
    if not owner:
        slot["event"].wait(180)
        if slot["error"] is not None:
            raise slot["error"]
        if slot["result"] is not None:
            return dict(slot["result"])
        raise NoFullSong("the lookup took too long")
    try:
        result = _find(line, key, duration_ms, source, extract)
        slot["result"] = result
        return dict(result)
    except Exception as exc:
        slot["error"] = exc
        raise
    finally:
        slot["event"].set()
        with _lock:
            _inflight.pop(key, None)


def _find(line, key, duration_ms, source, extract):
    t0 = time.time()
    timings = {}
    e = downloader.engine()
    extract = extract or (lambda page: _extract(e, page))
    found = {}

    def bandcamp():
        t = time.time()
        try:
            bc = e.search_bandcamp(line)
        except Exception:
            bc = {}
        found["bc"] = bc if (bc or {}).get("found") and bc.get("url") else None
        timings["bandcamp"] = round(time.time() - t, 1)

    def youtube():
        t = time.time()
        try:
            found["yt"] = _pick_youtube(e, line, int((duration_ms or 0) / 1000))
        except Exception:
            found["yt"] = None
        timings["youtube_search"] = round(time.time() - t, 1)

    def candidates():
        """(name, page) to try, in order; the searches run at the same time and YouTube is only waited for when
        Bandcamp has nothing."""
        threads = {}
        for name, fn, wanted in (("bc", bandcamp, source != downloader.SOURCE_YOUTUBE),
                                 ("yt", youtube, source != downloader.SOURCE_BANDCAMP)):
            if wanted:
                threads[name] = threading.Thread(target=fn, daemon=True)
                threads[name].start()
        if "bc" in threads:
            threads["bc"].join()
            if found.get("bc"):
                yield "Bandcamp", found["bc"]["url"]
        if "yt" in threads:
            threads["yt"].join()
            if found.get("yt"):
                yield "YouTube", found["yt"]

    last = None
    known = _pages.get(key)
    tried = set()
    if known:                                       # found before: no searches, just a fresh link
        tried.add(known[1])
        t = time.time()
        try:
            url, headers, seconds = extract(known[1])
            timings["extract"] = round(time.time() - t, 1); timings["total"] = round(time.time() - t0, 1)
            timings["searches"] = "remembered"
            result = {"url": url, "headers": headers, "page": known[1], "source": known[0],
                      "duration_ms": int((seconds or 0) * 1000), "timings": timings}
            with _lock:
                _cache[key] = (time.time(), dict(result))
            return result
        except Exception as exc:
            last = exc
            with _lock:
                _pages.pop(key, None)
    for name, page in candidates():
        if page in tried:
            continue
        t = time.time()
        try:
            url, headers, seconds = extract(page)
        except Exception as exc:              # e.g. a Bandcamp track that isn't streamable: try YouTube
            last = exc
            continue
        timings["extract"] = round(time.time() - t, 1); timings["total"] = round(time.time() - t0, 1)
        result = {"url": url, "headers": headers, "page": page, "source": name,
                  "duration_ms": int((seconds or 0) * 1000), "timings": timings}
        with _lock:
            _cache[key] = (time.time(), dict(result))
            _pages[key] = (name, page)
        _save_pages()
        return result
    raise NoFullSong(str(last) if last else "not found on Bandcamp or YouTube")


def youtube_page(artist, title, duration_ms=0, search=True):
    """The YouTube video matched to a song (for sharing): the one already used for streaming if there is one,
    otherwise found with the same matching (only when `search`). "" if none."""
    line = downloader.song_line(artist, title)
    with _lock:
        for (key_line, _src), (_t, res) in _cache.items():
            if key_line == line.casefold() and res.get("source") == "YouTube":
                return res.get("page", "")
    if not search:
        return ""
    try:
        e = downloader.engine()
        return _pick_youtube(e, line, int((duration_ms or 0) / 1000)) or ""
    except Exception:
        return ""


def clear_cache():
    global _preferred_attempt
    with _lock:
        _cache.clear()
        _pages.clear()
    _preferred_attempt = 0
    if _store_path:
        try:
            os.remove(_store_path)
        except OSError:
            pass


def download_original_audio(page, out_without_ext, progress=None, quality="best"):
    """Save a Bandcamp / YouTube page's audio as it comes (m4a, webm/opus or mp3), with no conversion, so it
    works where there's no ffmpeg (the Android app). Returns the saved file's path."""
    import os
    e = downloader.engine()
    if e.yt_dlp is None:
        raise NoFullSong("yt-dlp is not installed")
    hooks = []
    if progress is not None:
        def hook(d):
            if d.get("status") == "downloading" and d.get("total_bytes"):
                progress(d.get("downloaded_bytes", 0) / max(1, d["total_bytes"]))
        hooks.append(hook)
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True,
            # m4a first: every phone plays it and it carries cover art; then whatever audio there is
            "format": __import__("core.quality", fromlist=["x"]).audio_format(quality), "socket_timeout": 20,
            "outtmpl": out_without_ext.replace("%", "%%") + ".%(ext)s", "progress_hooks": hooks, "postprocessors": [],
            "allowed_extractors": e.SONG_EXTRACTORS, "extractor_args": e.yt_extractor_args()}
    with e.yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(page, download=True)
    path = (info or {}).get("requested_downloads", [{}])[0].get("filepath") or ""
    if not path:
        folder = os.path.dirname(out_without_ext) or "."
        base = os.path.basename(out_without_ext)
        found = [f for f in os.listdir(folder) if f.startswith(base + ".") and not f.endswith(".part")]
        path = os.path.join(folder, found[0]) if found else ""
    if not path or not os.path.exists(path):
        raise NoFullSong("the download didn't produce a file")
    return path


def download_full_song(artist, title, duration_ms, out_without_ext, source=downloader.SOURCE_BOTH, progress=None,
                       quality="best"):
    """Find the full song (same matching as streaming) and save its original audio. Returns (path, source)."""
    found = find_full_song(artist, title, duration_ms, source)
    try:
        return download_original_audio(found["page"], out_without_ext, progress, quality), found["source"]
    finally:
        cleanup_leftovers(out_without_ext)


def cleanup_leftovers(out_without_ext):
    """Remove half-finished files a download left behind (.part, .ytdl, thumbnails...)."""
    import os
    folder = os.path.dirname(out_without_ext) or "."
    base = os.path.basename(out_without_ext)
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        if name.startswith(base + ".") and name.lower().endswith((".part", ".ytdl", ".temp", ".jpg", ".jpeg",
                                                                    ".webp", ".png")):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
