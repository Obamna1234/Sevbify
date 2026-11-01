"""The Android app's door into Sevbify's shared core (the same core/ folder the Windows app uses).

Kotlin calls these functions through Chaquopy. Everything goes in and out as JSON text, so the Android side
stays simple and a change in core/ (search, radio, imports, podcasts, audiobooks, finding full songs, ...)
reaches both apps. No UI code here. Nothing is sent anywhere unless the app is online.
"""
import json
import os
import traceback

_state = {"net": None, "online": None, "music": None, "online_on": True, "source": "Bandcamp + YouTube"}


def _ok(value):
    return json.dumps({"ok": True, "value": value}, ensure_ascii=False)


_FRIENDLY = (
    ("confirm you\u2019re not a bot", "YouTube is blocking this connection for now (try again later or on another network)"),
    ("confirm you're not a bot", "YouTube is blocking this connection for now (try again later or on another network)"),
    ("Video unavailable", "that video isn't available"),
    ("HTTP Error 429", "too many requests right now; try again in a few minutes"),
)


def _readable(exc):
    """yt-dlp's errors are long and technical; show a short sentence for the common ones."""
    text = str(exc) or type(exc).__name__
    for needle, nice in _FRIENDLY:
        if needle.lower() in text.lower():
            return nice
    return text.replace("ERROR: ", "")[:300]


def _fail(exc):
    return json.dumps({"ok": False, "error": _readable(exc),
                       "trace": traceback.format_exc()[-1500:]}, ensure_ascii=False)


def _call(fn):
    def wrapped(*args):
        try:
            return _ok(fn(*args))
        except Exception as exc:          # every error goes back to Kotlin as text, never a crash
            return _fail(exc)
    wrapped.__name__ = fn.__name__
    return wrapped


def _track(t):
    d = t.to_dict()
    d["key"] = t.key
    return d


def _tracks(ts):
    return [_track(t) for t in ts]


def _show(s):
    d = s.to_dict()
    d["key"] = s.key
    return d


def _book(b):
    d = b.to_dict()
    d["key"] = b.key
    d["cover_url"] = b.cover_url
    return d


def _net():
    if _state["net"] is None:
        raise RuntimeError("setup() wasn't called")
    return _state["net"]


# --- start-up and settings ----------------------------------------------------------------------------------
@_call
def setup(data_dir, cache_dir, online=True, lastfm_key="", version=""):
    os.environ["SEVBIFY_DATA_DIR"] = data_dir
    if version:
        os.environ["SEVBIFY_VERSION"] = version
    os.makedirs(data_dir, exist_ok=True)
    from core.online.net import NetClient
    from core.online.providers import OnlineMusic
    _state["online_on"] = bool(online)
    _state["net"] = NetClient(cache_dir, enabled=lambda: _state["online_on"])
    _state["music"] = OnlineMusic(_state["net"], lastfm_key or "")
    from core.version import app_version
    return {"version": app_version()}


@_call
def set_online(on):
    _state["online_on"] = bool(on)
    return _state["online_on"]


@_call
def set_source(source):
    from core import downloader
    if source in downloader.SOURCES:
        _state["source"] = source
    return _state["source"]


# --- music --------------------------------------------------------------------------------------------------
@_call
def search(query, limit=30):
    return _tracks(_state["music"].search(query, int(limit)))


@_call
def search_artists(query, limit=10):
    return _state["music"].deezer.search_artists(query, int(limit))


@_call
def radio(artist, title="", limit=50):
    return _tracks(_state["music"].radio(artist, title, int(limit)))


@_call
def artist_card(name):
    return _state["music"].artist_card(name)


@_call
def artist_top(name, limit=10):
    d = _state["music"].deezer
    a = d.find_artist(name)
    if not a:
        return {"artist": None, "tracks": []}
    return {"artist": a, "tracks": _tracks(d.top_tracks(a.get("id"), int(limit)))}


@_call
def book_categories():
    from core import audiobooks
    return [{"name": n, "subject": q} for n, q in audiobooks.BOOK_CATEGORIES]


@_call
def artist_releases(name):
    """Albums, singles & EPs and compilations of an artist, newest first (for the artist page)."""
    d = _state["music"].deezer
    a = d.find_artist(name)
    if not a:
        return {"albums": [], "singles": [], "compilations": []}
    out = d.artist_albums(a.get("id"))
    for group in out.values():
        for album in group:
            album.setdefault("artist", {"name": a.get("name", name), "id": a.get("id")})
    return out


@_call
def profile_pack(json_text):
    """Your Sevbify profile file (base64 of its bytes; Kotlin / Swift write it where you chose)."""
    from core import profile
    return profile.pack_b64(json_text)


@_call
def profile_unpack(b64):
    from core import profile
    return profile.unpack_b64(b64)


@_call
def genres():
    return _state["music"].deezer.genres()


@_call
def genre_overview(genre_id):
    o = _state["music"].deezer.genre_overview(int(genre_id))
    o["tracks"] = _tracks(o["tracks"])
    return o


@_call
def playlist_tracks(playlist_id):
    return _tracks(_state["music"].deezer.playlist_tracks(playlist_id))


@_call
def album_for(artist, album):
    """The album a song is on (for "Go to album"), or None."""
    return _state["music"].deezer.find_album(artist, album)


@_call
def album_tracks(album_json):
    return _tracks(_state["music"].deezer.album_tracks(json.loads(album_json)))


@_call
def enrich(tracks_json):
    """Cover art / album / preview for songs that only have artist + title (e.g. imported ones)."""
    from core.online.models import OnlineTrack
    out = []
    for d in json.loads(tracks_json):
        t = OnlineTrack.from_dict(d)
        try:
            t = _state["music"].enrich(t)
        except Exception:
            pass
        out.append(_track(t))
    return out


@_call
def did_you_mean(query):
    """A corrected spelling when a finished search's results look unrelated (DuckDuckGo), or ""."""
    from core.online import spelling
    return spelling.did_you_mean(_state["net"], _state["music"], query)


@_call
def preview_url(artist, title):
    """The 30-second clip for a song (only for the song menu's Preview), or ""."""
    t = _state["music"].deezer.find_track(artist, title)
    return (t.preview_url if t is not None else "") or ""


@_call
def resolve(artist, title, duration_ms=0):
    """Full-length stream for a song you don't have: {"url", "headers", "page", "source", "duration_ms"}."""
    from core import streamer
    return streamer.find_full_song(artist, title, int(duration_ms or 0), _state["source"])


@_call
def download_song(artist, title, duration_ms, folder, quality="best"):
    from core import streamer, downloader
    out_dir = os.path.join(folder, downloader.artist_folder(artist))
    os.makedirs(out_dir, exist_ok=True)
    base = downloader.song_line(artist, title).replace("/", "-").replace("\\", "-")
    path, source = streamer.download_full_song(artist, title, int(duration_ms or 0), os.path.join(out_dir, base),
                                               _state["source"], quality=quality)
    return {"path": path, "source": source}


@_call
def download_url(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return _net().download(url, path)


# --- importing ----------------------------------------------------------------------------------------------
@_call
def import_link(text, song_links="", jamendo_client_id=""):
    from core import importers
    head = None
    if importers.parse_link(text) is not None:
        try:
            head = importers.fetch_from_link(_net(), text, jamendo_client_id)
        except importers.ImportError_:
            if not importers.parse_track_links(song_links):
                raise
    ids = importers.parse_track_links(song_links) or ([] if head else importers.parse_track_links(text))
    if ids:
        got = importers.fetch_tracks_from_links(_net(), song_links or text)
        head = dict(head or {"name": "Imported from Spotify", "cover_url": ""})
        head.update(tracks=got["tracks"], truncated=False, failed=got["failed"], chosic_url="")
    if head is None:
        raise importers.ImportError_(importers.LINK_HELP + ", or Spotify song links.")
    head["tracks"] = _tracks(head["tracks"])
    head["origin"] = importers.origin_of(text)
    return head


# --- your own music servers (Jellyfin, Nextcloud / WebDAV) ------------------------------------------------------
@_call
def server_add(kind, address, user, secret, folder=""):
    """Sign in. Returns the server (Jellyfin: a revocable token, not the password). The app keeps it privately."""
    from core import servers
    if kind == "jellyfin":
        return servers.jellyfin_sign_in(address, user, secret)
    return servers.webdav_connect(address, user, secret, folder)


@_call
def server_songs(server_json):
    from core import servers
    return _tracks(servers.songs(json.loads(server_json)))


@_call
def server_playable(server_json, track_json):
    """{"url", "headers"} to stream one of the server's songs (the sign-in travels only in the headers)."""
    from core import servers
    from core.online.models import OnlineTrack
    url, headers = servers.playable(json.loads(server_json), OnlineTrack.from_dict(json.loads(track_json)))
    return {"url": url, "headers": headers}


@_call
def server_download(server_json, track_json, folder):
    """Save a server song (straight from your server) into folder/<Artist>/. {"path"}."""
    from core import servers
    from core.online.models import OnlineTrack
    return {"path": servers.download(json.loads(server_json), OnlineTrack.from_dict(json.loads(track_json)), folder)}


@_call
def check_import(tracks_json):
    """Imported songs, looked up one by one: [{"status": ok / suggest / missing, "track", "suggestion" or None}].
    The app sends a few at a time to show progress."""
    from core import import_check
    from core.online.models import OnlineTrack
    tracks = [OnlineTrack.from_dict(d) for d in json.loads(tracks_json)]
    out = []
    for r in import_check.check_tracks(_state["music"], _state["net"], tracks):
        sug = r["suggestion"]
        out.append({"status": r["status"], "track": _track(r["track"]),
                    "suggestion": import_check.as_text(sug) if sug is not None else ""})
    return out


@_call
def import_file(path):
    from core import importers
    res = importers.read_playlist_file(path)
    items = []
    for kind, value in res["items"]:
        items.append({"kind": kind, "path": value} if kind == "file" else {"kind": "track", "track": _track(value)})
    return {"name": res["name"], "items": items}


# --- podcasts -----------------------------------------------------------------------------------------------
@_call
def top_shows(country="us"):
    from core import podcasts
    return [_show(s) for s in podcasts.top_shows(_net(), country)]


@_call
def podcast_categories():
    from core import podcasts
    return [{"id": i, "name": n} for i, n in podcasts.PODCAST_CATEGORIES]


@_call
def top_in_category(genre_id, country="us"):
    from core import podcasts
    return [_show(s) for s in podcasts.top_in_category(_net(), int(genre_id), country)]


@_call
def sponsor_segments(page_url):
    """Sponsor reads to skip in a YouTube episode (SponsorBlock; only a 4-character hash prefix is sent)."""
    from core import sponsorblock
    return sponsorblock.segments(_net(), page_url)


@_call
def search_podcasts(query, country="us", full=False):
    """full (the Podcasts chip): also the show's own YouTube channel when Apple doesn't have it. Otherwise (the All
    page) only shows whose name or host has the words you typed."""
    from core import podcasts
    if full:
        return [_show(s) for s in podcasts.search_with_youtube(_net(), query, 25, country)]
    return [_show(s) for s in podcasts.relevant(query, podcasts.search(_net(), query, 25, country))]


@_call
def show_link(text):
    """A pasted YouTube channel / playlist or RSS feed link, as a show to open."""
    from core import podcasts
    text = (text or "").strip()
    if podcasts.is_youtube_link(text):
        return _show(podcasts.Show(title="YouTube channel", feed_url=text, kind="youtube"))
    if text.startswith(("http://", "https://")):
        return _show(podcasts.Show(title="Podcast", feed_url=text))
    raise ValueError("Paste a YouTube channel link or a podcast feed (RSS) address.")


@_call
def fetch_show(show_json):
    from core import podcasts
    show, episodes = podcasts.fetch_show(_net(), podcasts.Show.from_dict(json.loads(show_json)))
    return {"show": _show(show), "note": podcasts.source_note(show),
            "episodes": [{"track": _track(e.track), "published": e.published, "date": e.date_text,
                          "description": e.description[:600], "guid": e.guid} for e in episodes]}


@_call
def youtube_stream(page_url, video=False):
    from core import podcasts
    url, headers = podcasts.youtube_stream(page_url, bool(video))
    return {"url": url, "headers": headers}


@_call
def download_youtube(page_url, out_without_ext, quality="best"):
    from core import streamer
    os.makedirs(os.path.dirname(out_without_ext), exist_ok=True)
    try:
        return streamer.download_original_audio(page_url, out_without_ext, quality=quality)
    finally:
        streamer.cleanup_leftovers(out_without_ext)


@_call
def youtube_video(page_url, quality="auto"):
    """Video + audio links for watching a video podcast at the chosen quality (Settings)."""
    from core import podcasts, quality as q
    return podcasts.youtube_video_streams(page_url, q.video_height(quality))


@_call
def youtube_channel_for(title, author=""):
    """A podcast's own YouTube channel (its video version), or None."""
    from core import podcasts
    show = podcasts.find_youtube_channel(title, author)
    return _show(show) if show else None


# --- audiobooks ---------------------------------------------------------------------------------------------
@_call
def books(kind="popular", query=""):
    from core import audiobooks
    fn = {"popular": lambda: audiobooks.popular(_net()), "newest": lambda: audiobooks.newest(_net()),
          "search": lambda: audiobooks.search(_net(), query),
          "category": lambda: audiobooks.in_category(_net(), query)}[kind]
    return [_book(b) for b in fn()]


@_call
def book_chapters(book_json, quality="standard"):
    from core import audiobooks
    book = audiobooks.Book.from_dict(json.loads(book_json))
    _book_details, tracks = audiobooks.chapters(_net(), book, quality)     # (book, [chapters])
    return _tracks(tracks)


# --- updates ------------------------------------------------------------------------------------------------
@_call
def check_updates(current, plat="android", fresh=False):
    """Newest Sevbify for this phone: {"newer", "latest", "url" (the .apk / .ipa), "sha256", "size", "message"}.
    `fresh` skips the 6-hour cache, for a manual "Check for updates"."""
    from core import updates
    return updates.check_app(_net(), current, plat, fresh=fresh)


@_call
def lyrics(artist, title, album="", duration_ms=0):
    """Lyrics for a song from LRCLIB ({"lines": [[ms, text]], "plain", "source", "synced"}), or None."""
    from core import lyrics as L
    net = _net() if _state["online_on"] else None
    got = L.find(net, artist, title, album or "", int(duration_ms or 0))
    return got.to_dict() if got else None


@_call
def share_links(artist, title, page_url="", duration_ms=0):
    """Spotify / YouTube / song.link links for sharing a song (looked up only when you press Share)."""
    from core import share, streamer
    if not _state["online_on"]:
        return dict(share.search_links(artist, title), songlink="", exact={"spotify": False, "youtube": False})
    # song.link first; YouTube is only searched when that didn't give a YouTube link (less sent to YouTube).
    yt = streamer.youtube_page(artist, title, int(duration_ms or 0), search=False)
    res = share.links(_net(), artist, title, page_url or "", yt)
    if not res["exact"].get("youtube"):
        yt = streamer.youtube_page(artist, title, int(duration_ms or 0), search=True)
        if yt:
            res = share.links(_net(), artist, title, page_url or "", yt)
    return res


@_call
def update_ytdlp():
    """Fetch the newest official yt-dlp (checksum-checked); it's used from the next start."""
    from core import updates
    changed, message = updates.update_ytdlp()
    return {"changed": changed, "message": message}


@_call
def ytdlp_info():
    from core import downloader
    e = downloader.engine()
    return {"version": e.ytdlp_version(), "age_days": e.ytdlp_age_days(), "updated_copy": bool(e.YTDLP_ACTIVE)}


@_call
def image(url):
    """Local file for a picture (downloaded once, then from the cache)."""
    return _net().cached_image(url) or _net().get_image(url) or ""
