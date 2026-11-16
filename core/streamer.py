"""Find a full-length stream for a song you don't have yet, with SEVBY's matching (no UI code).

Used when an online song (from Search or Radio) is played and Settings -> "Songs you don't have" is set to
"Full song": look on Bandcamp first, then YouTube (the same choice SEVBY makes when downloading), pick the
best match using the song's real length, and ask yt-dlp for a direct audio link that VLC can play. Nothing is
saved; the song stays "not downloaded" until you download it.

Streaming YouTube audio this way skips YouTube's own player (and its ads), which goes against YouTube's terms
of service, like downloading does. Sevbify shows this once, the first time, and the user decides.
"""
import json
import re
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
_PAGE_HOSTS = ("youtube.com", "youtu.be", "bandcamp.com", "soundcloud.com")
SOURCE_NAMES = ("Bandcamp", "YouTube", "SoundCloud")


def _page_ok(name, page):
    """A remembered page is only trusted when it is an https page on YouTube, Bandcamp or SoundCloud (the file is
    on disk)."""
    if name not in SOURCE_NAMES or not isinstance(page, str):
        return False
    try:
        u = urllib.parse.urlparse(page)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    if name == "SoundCloud" and not is_soundcloud_track(page):
        return False                               # one track only, never a profile or a set
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


private = False                  # Private session: nothing new is written to the page store


def _save_pages():
    if not _store_path or private:
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


DESKTOP_FALLBACK_CLIENTS = ("tv", "web_safari", "mweb", "android_vr")
def is_soundcloud_track(url):
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    parts = [x for x in u.path.split("/") if x]
    return u.scheme == "https" and host in ("soundcloud.com", "www.soundcloud.com", "m.soundcloud.com") \
        and len(parts) == 2 and parts[1] not in ("sets", "albums", "tracks", "reposts", "likes")


def _sc_search(e, query, n):
    """SoundCloud's search through yt-dlp: {"entries": [...]} (tests replace this: no real network)."""
    if e.yt_dlp is None:
        return {}
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
            "skip_download": True, "socket_timeout": 15, "allowed_extractors": ["soundcloud", "soundcloud:.*"]}
    with e.yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(f"scsearch{int(n)}:{query}", download=False) or {}


def _pick_soundcloud(e, line, duration_s):
    """SoundCloud: lots of music that's on neither Bandcamp nor YouTube (or not in the catalogue at all). Same
    rule as YouTube: the title must have most of the song title's words; and the length must be close when it is
    known, so a 30-second preview, a DJ mix or a different version isn't picked."""
    info = _sc_search(e, line, 8)
    artist, title = e._split_query(line)
    want = set(e._words(title or line))
    who = set(e._words(artist or ""))
    best, best_score = None, 0.0
    for entry in info.get("entries") or []:
        url = entry.get("webpage_url") or entry.get("url") or ""   # the search gives api links in "url"
        if not is_soundcloud_track(url):
            continue
        name = entry.get("title") or ""
        got = set(e._words(name))
        uploader = set(e._words(entry.get("uploader") or ""))
        if want and len(want & got) / len(want) < 0.6:
            continue
        if who and not who & (got | uploader):
            continue                                   # someone else's song with a similar name
        secs = entry.get("duration") or 0
        if duration_s and secs and abs(secs - duration_s) > max(12, 0.12 * duration_s):
            continue
        score = (len(want & got) / max(1, len(want))) + (0.5 if who and (who & (got | uploader)) else 0)
        if score > best_score:
            best, best_score = url, score
    return best


_preferred_attempt = 0           # which of the attempts below worked last time (tried first from then on)


def _attempts(e):
    """The yt-dlp settings to try for a link, fastest first. On the phones yt-dlp is told to ask several YouTube
    clients, one after the other, which is slow; a single fast client usually works, so those go first and the
    full list is the fallback. Desktop (no override) has just the one attempt."""
    base = dict(e.yt_extractor_args() or {})
    clients = list((base.get("youtube") or {}).get("player_client") or [])
    if not clients:
        # Desktop: yt-dlp's own choice first. Its link is checked before the player gets it; if YouTube refuses
        # it (seen on Windows: every first try ended at once and the song had to be saved to a file first), the
        # next client is asked instead of retrying the same kind of link.
        return [base] + [{"youtube": {"player_client": [c]}} for c in DESKTOP_FALLBACK_CLIENTS]
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
    e = downloader.engine() if downloader._engine is not None else None
    if e is not None and getattr(e, "yt_dlp", None) is not None:
        # Ask the way yt-dlp's downloads do (YouTube refused plain Python requests for links that downloaded
        # fine, so the check said "refused" for every YouTube client and the lookup took 15 s).
        try:
            from yt_dlp.networking import Request
            with e.yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "logger": e._QuietLogger(),
                                     "socket_timeout": timeout}) as ydl:
                with ydl.urlopen(Request(url, headers={**(headers or {}), "Range": "bytes=0-1"})) as r:
                    r.read(2)
                    return (getattr(r, "status", 200) or 200) < 400
        except Exception as exc:
            code = getattr(exc, "status", None) or getattr(getattr(exc, "response", None), "status", None)
            return not (isinstance(code, int) and code in (400, 401, 403, 404, 410))
    try:
        req = urllib.request.Request(url, headers={**(headers or {}), "Range": "bytes=0-1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(2)
            return r.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code not in (400, 401, 403, 404, 410)
    except Exception:
        return True


def _client_name(attempt):
    return "/".join((attempt.get("youtube") or {}).get("player_client") or ["default"])


def _note(text):
    try:
        from core import activity_log
        activity_log.log("stream", text)
    except Exception:
        pass


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
    from core import bandcamp
    if bandcamp.is_track_page(page):
        try:
            return bandcamp.stream(page)          # Bandcamp's own player link (yt-dlp's reader needs curl_cffi now)
        except Exception:
            pass                                  # page changed: try yt-dlp below
    if e.yt_dlp is None:
        raise NoFullSong("yt-dlp is not installed")
    attempts = _attempts(e)
    order = list(range(_preferred_attempt, len(attempts))) + list(range(0, min(_preferred_attempt, len(attempts))))
    last = None
    for i in order:
        fmt = __import__("core.quality", fromlist=["x"]).STREAM_AUDIO_FORMAT
        if is_soundcloud_track(page):      # a plain MP3 when SoundCloud has one (every player can stream it), else HLS
            fmt = "bestaudio[protocol^=http][protocol!*=m3u8]/" + fmt
        opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "noplaylist": True,
                "format": fmt,
                "socket_timeout": 15 if len(attempts) > 1 else 20,
                "skip_download": True, "allowed_extractors": e.SONG_EXTRACTORS, "extractor_args": attempts[i]}
        try:
            with e.yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(page, download=False)
            url = (info or {}).get("url")
            if not url:
                raise NoFullSong("no playable audio link")
            if is_soundcloud_track(page) and ("preview" in str(info.get("format_id", "")).lower()
                                             or 0 < (info.get("duration") or 0) <= 35):
                raise NoFullSong("SoundCloud only has a 30-second preview of this one (Go+)")
            headers = dict(info.get("http_headers") or {})
            if i != order[-1] and not url_works(url, headers):       # refused: this client's links don't play, try the next
                raise NoFullSong("the link was refused")
        except Exception as exc:
            last = exc
            site = "Bandcamp" if "bandcamp.com" in page else "SoundCloud" if "soundcloud.com" in page else "YouTube"
            _note(f"{site} link {_client_name(attempts[i])}: {str(exc)[:160]}")
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
    search_errors = {}                  # why a search came back empty (kept for the message, e.g. "not a bot")

    def bandcamp():
        t = time.time()
        try:
            bc = e.search_bandcamp(line)
        except Exception as exc:
            bc = {}
            search_errors["Bandcamp"] = str(exc)[:300]
        found["bc"] = bc if (bc or {}).get("found") and bc.get("url") else None
        if not found["bc"] and (bc or {}).get("error"):
            search_errors["Bandcamp"] = str(bc["error"])[:300]          # refused / failed, not "not there"
        timings["bandcamp"] = round(time.time() - t, 1)

    def youtube():
        t = time.time()
        try:
            found["yt"] = _pick_youtube(e, line, int((duration_ms or 0) / 1000))
        except Exception as exc:
            found["yt"] = None
            search_errors["YouTube"] = str(exc)[:300]
        timings["youtube_search"] = round(time.time() - t, 1)

    def soundcloud():
        t = time.time()
        try:
            found["sc"] = _pick_soundcloud(e, line, int((duration_ms or 0) / 1000))
        except Exception as exc:
            found["sc"] = None
            search_errors["SoundCloud"] = str(exc)[:300]
        timings["soundcloud"] = round(time.time() - t, 1)

    def candidates():
        """(name, page) to try, in order; the searches run at the same time and YouTube is only waited for when
        Bandcamp has nothing, SoundCloud when neither has it."""
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
        if source == downloader.SOURCE_BOTH:
            soundcloud()       # only asked when the others had nothing playable (one site fewer per song)
            if found.get("sc"):
                yield "SoundCloud", found["sc"]

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
            search_errors[name + " link"] = str(exc)[:300]
            continue
        timings["extract"] = round(time.time() - t, 1); timings["total"] = round(time.time() - t0, 1)
        result = {"url": url, "headers": headers, "page": page, "source": name,
                  "duration_ms": int((seconds or 0) * 1000), "timings": timings,
                  "skipped": dict(search_errors)}          # why an earlier place wasn't used (for the logs)
        with _lock:
            _cache[key] = (time.time(), dict(result))
            _pages[key] = (name, page)
        _save_pages()
        return result
    if last and len(search_errors) <= 1:
        raise NoFullSong(str(last))
    why = "; ".join(f"{k} search failed: {v}" for k, v in search_errors.items())
    raise NoFullSong("not found on Bandcamp, YouTube or SoundCloud" + (f" ({why})" if why else ""))


def remember_page(artist, title, source_name, page):
    """A song picked straight from a site's own search (e.g. "On SoundCloud" in Search): play / download exactly
    that page instead of searching for the song again."""
    if not _page_ok(source_name, page):
        return False
    line = downloader.song_line(artist, title)
    with _lock:
        for src in (downloader.SOURCE_BOTH,):
            _pages[(line.casefold(), src)] = (source_name, page)
    _save_pages()
    return True


def remembered_page(artist, title, source_name):
    line = downloader.song_line(artist, title)
    with _lock:
        for (key_line, _src), (name, page) in _pages.items():
            if key_line == line.casefold() and name == source_name:
                return page
    return ""


def search_soundcloud(query, limit=10):
    """Songs on SoundCloud for a search (for the "On SoundCloud" part of Search): [OnlineTrack]."""
    from core.online.models import OnlineTrack
    info = _sc_search(downloader.engine(), query, limit)
    out = []
    for entry in info.get("entries") or []:
        url = entry.get("webpage_url") or entry.get("url") or ""   # the search gives api links in "url"
        if not is_soundcloud_track(url) or not entry.get("title"):
            continue
        secs = entry.get("duration") or 0
        if 0 < secs <= 35:
            continue                                   # a preview or a jingle
        title = entry["title"]
        artist = ((entry.get("artists") or [None])[0]) or entry.get("uploader") or ""   # the label's artist name
        # Uploads are often named "Artist - Title" (or "Artist : Title") by someone else: the uploader isn't the
        # artist then (beta.47: "Abyssic Hate : Bloodletting" by "Rob_rob_" went to Rob_rob_'s page).
        m = re.match(r"^\s*(.{1,60}?)\s+[-–—:|]\s+(.+)$", title)
        if m:
            artist, title = m.group(1), m.group(2)
        thumbs = entry.get("thumbnails") or []
        cover = (thumbs[-1].get("url") if thumbs and isinstance(thumbs[-1], dict) else "") or entry.get("thumbnail") or ""
        out.append(OnlineTrack(title=title.strip(), artist=artist.strip() or "SoundCloud", duration_ms=int(secs * 1000),
                               cover_url=cover if str(cover).startswith("https://") else "", source="soundcloud",
                               page_url=url))
    return out


def _sc_api(path, query, ident="sevbify"):
    """SoundCloud's public API through yt-dlp's SoundCloud reader (it handles SoundCloud's client id).
    Tests replace this."""
    e = downloader.engine()
    if e.yt_dlp is None:
        return {}
    with e.yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "logger": e._QuietLogger(),
                             "socket_timeout": 15}) as ydl:
        ie = ydl.get_info_extractor("SoundcloudSearch")
        ie.initialize()
        return ie._call_api(ie._API_V2_BASE + path, ident, query=query, headers=ie._HEADERS) or {}


def _artwork(url, size="t500x500"):
    url = url or ""
    return re.sub(r"-(large|t\d+x\d+|crop|original)\.(jpg|png)$", rf"-{size}.\2", url) if url.startswith("https://") else ""


def soundcloud_albums(artist, limit=12):
    """The artist's albums and EPs on SoundCloud, like a Spotify discography: [{"title", "url", "cover", "year",
    "count", "kind"}]. Only ones credited to this artist (the label's artist name, the uploader, or a title like
    "Artist - Album"), each with its own cover; the same album uploaded twice is listed once."""
    words = lambda t: re.findall(r"\w+", (t or "").casefold())
    want = words(artist)
    data = _sc_api("search/albums", {"q": artist, "limit": max(limit * 2, 20)})
    out, seen = [], set()
    for item in (data or {}).get("collection") or []:
        url = item.get("permalink_url") or ""
        title = item.get("title") or ""
        pub = item.get("publisher_metadata") or {}
        user = (item.get("user") or {}).get("username") or ""
        m = re.match(r"^\s*(.{1,60}?)\s+[-–—:|]\s+(.+)$", title)
        credited = pub.get("artist") or (m.group(1) if m else "") or user
        if words(credited) != want or not url.startswith("https://soundcloud.com/") or "/sets/" not in url:
            continue
        name = m.group(2) if m and words(m.group(1)) == want else title
        key = tuple(words(name))
        if key in seen:
            continue
        seen.add(key)
        kind = {"album": "Album", "ep": "EP", "single": "Single", "compilation": "Compilation"}.get(
            (item.get("set_type") or "").lower(), "Album")
        out.append({"title": name, "url": url, "cover": _artwork(item.get("artwork_url")),
                    "year": (item.get("release_date") or item.get("display_date") or item.get("created_at") or "")[:4],
                    "count": int(item.get("track_count") or 0), "kind": kind, "artist": artist})
        if len(out) >= limit:
            break
    return out


def soundcloud_album_tracks(album):
    """The songs of a SoundCloud album (from soundcloud_albums), in order, as OnlineTracks credited to the artist."""
    from core.online.models import OnlineTrack
    if not is_soundcloud_set(album.get("url")):
        return []
    e = downloader.engine()
    if e.yt_dlp is None:
        return []
    opts = {"quiet": True, "no_warnings": True, "logger": e._QuietLogger(), "extract_flat": True,
            "skip_download": True, "socket_timeout": 15, "allowed_extractors": ["soundcloud:set", "soundcloud"]}
    with e.yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(album["url"], download=False) or {}
    out = []
    for entry in info.get("entries") or []:
        url = entry.get("webpage_url") or entry.get("url") or ""
        title = entry.get("title") or entry.get("track") or ""
        if not title:
            continue
        m = re.match(r"^\s*(.{1,60}?)\s+[-–—:|]\s+(.+)$", title)
        if m and re.findall(r"\w+", m.group(1).casefold()) == re.findall(r"\w+", album["artist"].casefold()):
            title = m.group(2)
        out.append(OnlineTrack(title=title.strip(), artist=album["artist"], album=album["title"],
                               duration_ms=int((entry.get("duration") or 0) * 1000), cover_url=album.get("cover", ""),
                               source="soundcloud", page_url=url if is_soundcloud_track(url) else ""))
    return [t for t in out if t.page_url]


def is_soundcloud_set(url):
    try:
        u = urllib.parse.urlparse(url or "")
    except ValueError:
        return False
    parts = [x for x in u.path.split("/") if x]
    return u.scheme == "https" and (u.hostname or "").lower() in ("soundcloud.com", "www.soundcloud.com") \
        and len(parts) == 3 and parts[1] == "sets"


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
    from core import bandcamp
    if bandcamp.is_track_page(page):
        try:
            return bandcamp.download(page, out_without_ext + ".mp3") and out_without_ext + ".mp3"
        except Exception:
            pass                                  # page changed: try yt-dlp below
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
